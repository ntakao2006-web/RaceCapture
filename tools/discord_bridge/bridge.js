// Discord voice channel <-> ecorun-logger-server room (ER-10-8).
//
// The pit talks on Discord (iPhone/Android keep the call in the background,
// push-to-talk enforced by the channel's permissions); the driver talks through
// the logger, which only ever connects to our server. This bot joins both:
//
//   room -> Discord: the bot connects to /ws/audio/<room> as a "mix listener"
//     (the same 8 kHz / 120 ms mix the logger gets, ER-10-6), so it hears
//     everyone talking in the room except itself, and plays that into Discord.
//   Discord -> room: it decodes each Discord speaker (48 kHz stereo Opus),
//     downsamples to 8 kHz mono, mixes, and sends 60 ms Opus packets with
//     audio.ptt on while someone is talking (the server only mixes talkers).
//
// Neither side hears itself: Discord does not deliver the bot's own audio, and
// the server's mix leaves out the listener's own voice.
//
// Env: DISCORD_TOKEN, DISCORD_GUILD_ID, DISCORD_CHANNEL_ID,
//      ECORUN_URL (default ws://127.0.0.1:3000), ECORUN_ROOM (default home-test).
// Slash command /ecologger join [channel] [room] | leave | status moves the bot;
// the result is kept in STATE_FILE (default ./state.json) and wins over
// DISCORD_CHANNEL_ID / ECORUN_ROOM after a restart.
// DRY_RUN=tone|listen skips Discord: "tone" sends a 3 s test tone into the room,
// "listen" counts the mix packets it gets (to test the server side without a token).
'use strict';

const fs = require('fs');
const path = require('path');
const OpusScript = require('opusscript');
const WebSocket = require('ws');

const ECORUN_URL = process.env.ECORUN_URL || 'ws://127.0.0.1:3000';
const ROOM = process.env.ECORUN_ROOM || 'home-test';
const DRY_RUN = process.env.DRY_RUN || '';
const GUILD_ID = process.env.DISCORD_GUILD_ID;
const STATE_FILE = process.env.STATE_FILE || path.join(__dirname, 'state.json');
const ROOM_NAME = /^[A-Za-z0-9_-]{1,64}$/;

const ROOM_RATE = 8000;          // server format (src/audio.rs)
const SEND_FRAME = 480;          // 60 ms at 8 kHz, the server's frame
const MIX_FORMAT = { sample_rate: 8000, channels: 1, frame_ms: 120 };  // logger mix (src/mixer.rs)
const DISCORD_RATE = 48000;
const RATIO = DISCORD_RATE / ROOM_RATE;  // 6
const PTT_OFF_MS = 500;          // release ptt this long after the last Discord audio
const MAX_BUFFER = SEND_FRAME * 4;
// /ecologger audio options: [option, description, min, max]; ranges match voice_agent.SETTINGS.
const AUDIO_OPTIONS = [
  ['level', 'ドライバーの声の大きさの目標 dBFS（大きいほど大きい。標準 -16）', -30, -6],
  ['max_gain', 'マイクの増幅の上限 dB（上げると小さいマイクでも大きくなるが雑音も増える。標準 30）', 0, 40],
  ['lowcut', '低音カット Hz（上げると風切り音が減る。0でなし。標準 250）', 0, 400],
  ['bitrate', 'ドライバーの声のビットレート kbps（上げると音質が上がるがLTEの通信量が増える。標準 6）', 6, 16],
  ['volume', 'ドライバーのイヤホンの音量 %（標準 80）', 0, 100],
];
const AUDIO_KEYS = { level: 'level_db', max_gain: 'max_gain_db', lowcut: 'lowcut_hz', bitrate: 'bitrate', volume: 'volume' };

const log = (...a) => console.log(new Date().toISOString(), ...a);

// ---- resampling ----------------------------------------------------------
// 48 kHz -> 8 kHz: windowed-sinc low-pass at 3.4 kHz, then keep every 6th sample.
const TAPS = (() => {
  const n = 63, fc = 3400 / DISCORD_RATE, h = new Float32Array(n);
  let sum = 0;
  for (let i = 0; i < n; i++) {
    const m = i - (n - 1) / 2;
    const sinc = m === 0 ? 2 * fc : Math.sin(2 * Math.PI * fc * m) / (Math.PI * m);
    h[i] = sinc * (0.54 - 0.46 * Math.cos(2 * Math.PI * i / (n - 1)));
    sum += h[i];
  }
  return h.map((v) => v / sum);
})();

class Downsampler {
  constructor() { this.hist = new Float32Array(TAPS.length - 1); }
  // stereo s16 at 48 kHz (interleaved) -> mono float at 8 kHz
  push(pcm) {
    const frames = pcm.length / 2;
    const x = new Float32Array(this.hist.length + frames);
    x.set(this.hist);
    for (let i = 0; i < frames; i++) x[this.hist.length + i] = (pcm[2 * i] + pcm[2 * i + 1]) / 2;
    const out = new Float32Array(Math.floor(frames / RATIO));
    for (let o = 0; o < out.length; o++) {
      const end = this.hist.length + (o + 1) * RATIO - 1;
      let acc = 0;
      for (let k = 0; k < TAPS.length; k++) acc += TAPS[k] * x[end - k];
      out[o] = acc;
    }
    this.hist = x.slice(x.length - this.hist.length);
    return out;
  }
}

// 8 kHz mono -> 48 kHz stereo s16, linear interpolation (voice band only, good enough).
class Upsampler {
  constructor() { this.last = 0; }
  push(mono) {
    const out = new Int16Array(mono.length * RATIO * 2);
    for (let i = 0; i < mono.length; i++) {
      for (let k = 0; k < RATIO; k++) {
        const v = this.last + (mono[i] - this.last) * (k + 1) / RATIO;
        const j = (i * RATIO + k) * 2;
        out[j] = out[j + 1] = v;
      }
      this.last = mono[i];
    }
    return out;
  }
}

// ---- room -> Discord as one endless stream ---------------------------------
// Every OpusScript instance takes WASM heap that is never given back, and once the heap
// grows the arrays of the older instances are detached: encode() then throws "offset is
// out of bounds" (the bot crashed 7 times on 2026-10-22; a test broke after 75 instances,
// 0.1.1 after 109). A new audio resource per talk spurt made a new encoder each time, so
// the player gets one stream for good: room audio when there is some, silence otherwise.
const DISCORD_FRAME = DISCORD_RATE / 50 * 2 * 2;  // 20 ms of 48 kHz stereo s16, in bytes
const ROOM_QUEUE_MAX = DISCORD_RATE * 2 * 2;       // 1 s; behind that, drop the oldest

class RoomStream extends require('stream').Readable {
  constructor() {
    super({ highWaterMark: DISCORD_FRAME });
    this.queue = [];
    this.queued = 0;
  }
  feed(buf) {
    this.queue.push(buf);
    this.queued += buf.length;
    while (this.queued > ROOM_QUEUE_MAX) this.queued -= this.queue.shift().length;
  }
  _read() {
    if (this.queued < DISCORD_FRAME) { this.push(Buffer.alloc(DISCORD_FRAME)); return; }
    const out = Buffer.alloc(DISCORD_FRAME);
    let filled = 0;
    while (filled < DISCORD_FRAME) {
      const head = this.queue[0], use = Math.min(head.length, DISCORD_FRAME - filled);
      head.copy(out, filled, 0, use);
      filled += use;
      if (use === head.length) this.queue.shift(); else this.queue[0] = head.subarray(use);
    }
    this.queued -= DISCORD_FRAME;
    this.push(out);
  }
}

const toInt16 = (buf) => new Int16Array(buf.buffer, buf.byteOffset, buf.length / 2);
const clip = (v) => Math.max(-32768, Math.min(32767, Math.round(v)));

// ---- the server room -----------------------------------------------------
class Room {
  constructor(name, onMix, onControl = () => {}) {
    this.name = name;
    this.onMix = onMix;
    this.onControl = onControl;
    this.ws = null;
    this.ptt = false;
    this.connect();
  }
  connect() {
    const name = this.name;
    const url = `${ECORUN_URL}/ws/audio/${encodeURIComponent(name)}`;
    const ws = this.ws = new WebSocket(url);
    ws.on('open', () => {
      log(`room ${name}: connected`);
      this.ptt = false;
      ws.send(JSON.stringify({ type: 'hello', client_id: 'discord-bridge', protocol: 1, audio_formats: [MIX_FORMAT] }));
    });
    ws.on('message', (data, binary) => {
      if (ws !== this.ws) return;
      if (binary) this.onMix(data);
      else { try { this.onControl(JSON.parse(data.toString())); } catch { /* not JSON */ } }
    });
    ws.on('close', () => {
      if (ws !== this.ws) return;  // switched to another room
      log(`room ${name}: closed, reconnecting`);
      setTimeout(() => { if (ws === this.ws) this.connect(); }, 2000);
    });
    ws.on('error', (e) => log(`room ${name}: ${e.message}`));
  }
  // Move to another room (another car). The old socket is closed without reconnecting.
  switchTo(name) {
    if (name === this.name) return;
    const old = this.ws;
    this.name = name;
    this.connect();
    old.close();
  }
  get connected() { return this.ws.readyState === WebSocket.OPEN; }
  setPtt(active) {
    if (active === this.ptt || this.ws.readyState !== WebSocket.OPEN) return;
    this.ptt = active;
    this.ws.send(JSON.stringify({ type: 'audio.ptt', active }));
  }
  sendJson(event) {
    if (this.ws.readyState !== WebSocket.OPEN) return false;
    this.ws.send(JSON.stringify(event));
    return true;
  }
  sendOpus(packet) {
    if (this.ws.readyState === WebSocket.OPEN) this.ws.send(packet);
  }
}

// Mixes everyone speaking on Discord into 60 ms frames for the room.
class DiscordToRoom {
  constructor(room) {
    this.room = room;
    this.sources = new Map();  // userId -> {decoder, down, buf: Float32Array[], at}
    this.encoder = new OpusScript(ROOM_RATE, 1, OpusScript.Application.VOIP);
    this.encoder.encoderCTL(4002, 12000);  // OPUS_SET_BITRATE_REQUEST
    this.lastAudio = 0;
    setInterval(() => this.tick(), 60);
  }
  source(userId) {
    let s = this.sources.get(userId);
    if (!s) {
      s = { decoder: new OpusScript(DISCORD_RATE, 2), down: new Downsampler(), buf: [] , len: 0 };
      this.sources.set(userId, s);
    }
    return s;
  }
  pushOpus(userId, packet) {
    const s = this.source(userId);
    let pcm;
    try { pcm = toInt16(s.decoder.decode(packet)); } catch { return; }
    this.pushPcm(s, s.down.push(pcm));
  }
  pushPcm(s, mono) {
    s.buf.push(mono); s.len += mono.length;
    while (s.len > MAX_BUFFER) s.len -= s.buf.shift().length;  // fell behind: drop the oldest
    this.lastAudio = Date.now();
  }
  take(s, n) {
    const out = new Float32Array(n);
    let filled = 0;
    while (filled < n && s.buf.length) {
      const head = s.buf[0], use = Math.min(head.length, n - filled);
      out.set(head.subarray(0, use), filled); filled += use;
      if (use === head.length) s.buf.shift(); else s.buf[0] = head.subarray(use);
    }
    s.len -= filled;
    return out;
  }
  tick() {
    const ready = [...this.sources.values()].filter((s) => s.len >= SEND_FRAME);
    if (ready.length) {
      const mix = new Float32Array(SEND_FRAME);
      for (const s of ready) { const f = this.take(s, SEND_FRAME); for (let i = 0; i < SEND_FRAME; i++) mix[i] += f[i]; }
      const pcm = new Int16Array(SEND_FRAME);
      for (let i = 0; i < SEND_FRAME; i++) pcm[i] = clip(mix[i]);
      this.room.setPtt(true);
      this.room.sendOpus(this.encoder.encode(Buffer.from(pcm.buffer), SEND_FRAME));
    } else if (this.room.ptt && Date.now() - this.lastAudio > PTT_OFF_MS) {
      this.room.setPtt(false);
    }
  }
  // A speaker stopped: forget the queued sound but keep the decoder (a new OpusScript per
  // utterance is what wore out the WASM heap, see RoomStream).
  drop(userId) {
    const s = this.sources.get(userId);
    if (s) { s.buf = []; s.len = 0; }
  }
}

// ---- dry runs (no Discord) ------------------------------------------------
function dryRun() {
  if (DRY_RUN === 'listen') {
    const decoder = new OpusScript(ROOM_RATE, 1);
    let packets = 0, bytes = 0, peak = 0;
    new Room(ROOM, (p) => {
      packets++; bytes += p.length;
      const pcm = toInt16(decoder.decode(p));
      for (const v of pcm) peak = Math.max(peak, Math.abs(v));
    });
    setInterval(() => { log(`mix received: ${packets} packets, ${bytes} bytes, peak ${peak}`); peak = 0; }, 2000);
    return;
  }
  // tone: 440 Hz as if a Discord user spoke for 3 s, fed through the real 48 kHz path
  const room = new Room(ROOM, () => {});
  const up = new DiscordToRoom(room);
  const encoder48 = new OpusScript(DISCORD_RATE, 2, OpusScript.Application.VOIP);
  let t = 0, frames = 0;
  setTimeout(() => {
    const timer = setInterval(() => {
      const pcm = new Int16Array(960 * 2);
      for (let i = 0; i < 960; i++, t++) pcm[2 * i] = pcm[2 * i + 1] = 8000 * Math.sin(2 * Math.PI * 440 * t / DISCORD_RATE);
      up.pushOpus('tone', encoder48.encode(Buffer.from(pcm.buffer), 960));
      if (++frames >= 150) { clearInterval(timer); log('tone done'); setTimeout(() => process.exit(0), 1500); }
    }, 20);
  }, 1000);
}

// ---- Discord ---------------------------------------------------------------
function discord() {
  const { Client, GatewayIntentBits, Events, SlashCommandBuilder, ChannelType, MessageFlags } = require('discord.js');
  const {
    joinVoiceChannel, createAudioPlayer, createAudioResource, StreamType, NoSubscriberBehavior,
    AudioPlayerStatus, EndBehaviorType, VoiceConnectionStatus, entersState,
  } = require('@discordjs/voice');
  const prism = require('prism-media');   // comes with @discordjs/voice

  const client = new Client({ intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildVoiceStates] });
  const decoder8k = new OpusScript(ROOM_RATE, 1);
  const up = new Upsampler();
  const player = createAudioPlayer({ behaviors: { noSubscriber: NoSubscriberBehavior.Play, maxMissedFrames: 50 } });
  // room -> Discord: one endless resource (RoomStream). Only if the player ever stops
  // is a new one made.
  // The encoder is made here (not by createAudioResource) to keep its read-ahead to two
  // frames: by default the streams would queue some 400 ms of silence ahead of the voice.
  let stream = null;
  const play = () => {
    stream = new RoomStream();
    const encoder = new prism.opus.Encoder({ rate: DISCORD_RATE, channels: 2, frameSize: DISCORD_FRAME / 4,
      readableHighWaterMark: 2, writableHighWaterMark: DISCORD_FRAME });
    player.play(createAudioResource(stream.pipe(encoder), { inputType: StreamType.Opus }));
  };
  player.on(AudioPlayerStatus.Idle, () => { log('player idle, restarting the stream'); play(); });
  player.on('error', (e) => { log('player:', e.message); });
  play();

  // The logger's answers to /ecologger audio (logger.config through the server).
  let loggerConfig = null;
  const configWaiters = [];
  const state = loadState();
  const room = new Room(state.room || ROOM, (packet) => {
    let mono;
    try { mono = toInt16(decoder8k.decode(packet)); } catch { return; }
    stream.feed(Buffer.from(up.push(mono).buffer));
  }, (event) => {
    if (event.type !== 'logger.config' || !event.data) return;
    loggerConfig = event.data;
    configWaiters.splice(0).forEach((resolve) => resolve(event.data));
  });
  const down = new DiscordToRoom(room);

  // The voice channel we want to be in (null after /ecologger leave). Saved with the
  // room so a restart goes back to where the last command put us.
  let wantChannel = state.channelId === undefined ? (process.env.DISCORD_CHANNEL_ID || null) : state.channelId;
  let connection = null;
  const prepared = new WeakSet();

  async function join(channelId) {
    const guild = await client.guilds.fetch(GUILD_ID);
    // joinVoiceChannel moves an existing connection in this guild instead of making a new one
    const c = connection = joinVoiceChannel({
      guildId: guild.id, channelId,
      adapterCreator: guild.voiceAdapterCreator, selfDeaf: false, selfMute: false,
    });
    if (prepared.has(c)) return;
    prepared.add(c);
    c.subscribe(player);
    c.on(VoiceConnectionStatus.Ready, () => log(`discord voice: ready (${c.joinConfig.channelId})`));
    c.on(VoiceConnectionStatus.Disconnected, async () => {
      try {
        await Promise.race([
          entersState(c, VoiceConnectionStatus.Signalling, 5000),
          entersState(c, VoiceConnectionStatus.Connecting, 5000),
        ]);
      } catch {
        if (c !== connection) return;
        log('discord voice: lost, rejoining');
        c.destroy();
        connection = null;
        setTimeout(() => { if (wantChannel && !connection) join(wantChannel).catch((e) => log('join failed:', e.message)); }, 3000);
      }
    });
    // Discord -> room
    c.receiver.speaking.on('start', (userId) => {
      if (c.receiver.subscriptions.has(userId)) return;
      const opus = c.receiver.subscribe(userId, { end: { behavior: EndBehaviorType.AfterSilence, duration: 400 } });
      opus.on('data', (packet) => down.pushOpus(userId, packet));
      opus.on('end', () => down.drop(userId));
      opus.on('error', (e) => log(`receive ${userId}:`, e.message));
    });
  }

  function leave() {
    if (connection) { connection.destroy(); connection = null; }
  }

  // ---- /ecologger join|leave|status ----------------------------------------
  // One parent command, so it never collides with other bots' /join and /leave
  // (the team's ecorun-talk bot already uses those two).
  const command = new SlashCommandBuilder()
    .setName('ecologger').setDescription('EcoLoggerの中継Bot（ロガーの部屋 ⇔ このボイスチャンネル）')
    .addSubcommand((s) => s.setName('join').setDescription('ボイスチャンネルに入ってロガーの部屋とつなぐ')
      .addChannelOption((o) => o.setName('channel').setDescription('入るボイスチャンネル（省略時は呼んだ人がいる所）')
        .addChannelTypes(ChannelType.GuildVoice))
      .addStringOption((o) => o.setName('room').setDescription('つなぐロガーの部屋（省略時は今の部屋）').setMaxLength(64)))
    .addSubcommand((s) => s.setName('leave').setDescription('ボイスチャンネルから出る（再起動しても戻らない）'))
    .addSubcommand((s) => s.setName('status').setDescription('いまの接続先を表示'))
    .addSubcommand((s) => {
      s.setName('audio').setDescription('ロガーの音声の設定を見る・変える（何も指定しなければ見るだけ）');
      for (const [name, text, min, max] of AUDIO_OPTIONS) {
        s.addIntegerOption((o) => o.setName(name).setDescription(text).setMinValue(min).setMaxValue(max));
      }
      return s;
    });

  // Ask the logger in the room (logger.config) and wait for its answer: on LTE it reads
  // the server every 2 s, so up to about 6 s.
  async function askLogger(voice) {
    if (!room.sendJson({ type: 'logger.config', data: { voice } })) return null;
    return new Promise((resolve) => {
      configWaiters.push(resolve);
      setTimeout(() => { const i = configWaiters.indexOf(resolve); if (i >= 0) { configWaiters.splice(i, 1); resolve(null); } }, 8000);
    });
  }

  // Each line: what it is now, what changing it does, and the option to change it with,
  // so the pit can act on the reply alone (asked for on 2026-10-23).
  function audioText(c) {
    const v = c.voice || {};
    const atMax = c.gain_db !== undefined && v.max_gain_db !== undefined && c.gain_db >= v.max_gain_db - 0.5;
    return [
      `**ドライバーの声の大きさ** ${v.level_db} dBFS（-30〜-6、標準 -16）`,
      '　声が小さい → 上げる（例 `level:-12`）／大きすぎ・割れる → 下げる',
      `**増幅の上限** ${v.max_gain_db} dB（0〜40、標準 30）　いまの増幅 ${c.gain_db} dB${atMax ? '（上限に達している）' : ''}`,
      '　上限に達していて声が小さい → 上げる（例 `max_gain:36`）／雑音が大きい → 下げる',
      `**低音カット** ${v.lowcut_hz ? `${v.lowcut_hz} Hz` : 'なし'}（0〜400、標準 250）`,
      '　風切り音・ゴーという音が大きい → 上げる（例 `lowcut:350`）／声がこもる・細い → 下げる',
      `**ビットレート** ${v.bitrate / 1000} kbps（6〜16、標準 6）`,
      '　声がガビガビ → 上げる（例 `bitrate:10`）。上げるほどLTEの通信量が増え、テレメトリを圧迫しうる',
      `**ドライバーのイヤホンの音量** ${v.volume}%（0〜100、標準 80）`,
      '　ドライバーがピットの声を聞き取れない → 上げる（例 `volume:95`）',
      `マイク: ${c.mic ? c.device : 'なし（USBのマイク・イヤホンが挿さっているか）'}`,
      '複数まとめて変えられる（例 `/ecologger audio level:-12 lowcut:300`）。値はロガーの再起動後も残る',
    ].join('\n');
  }

  function statusText() {
    const vs = connection ? connection.state.status : 'not joined';
    return [
      `部屋: \`${room.name}\`（${room.connected ? '接続中' : '切断中'}）`,
      `ボイスチャンネル: ${connection ? `<#${connection.joinConfig.channelId}>` : 'なし'}（${vs}）`,
      `Discord→部屋で送信中: ${room.ptt ? 'はい' : 'いいえ'}`,
    ].join('\n');
  }

  async function onCommand(it) {
    const sub = it.options.getSubcommand();
    const reply = (content) => it.reply({ content, flags: MessageFlags.Ephemeral });
    if (sub === 'status') return reply(statusText());
    if (sub === 'audio') {
      const voice = {};
      for (const [name] of AUDIO_OPTIONS) {
        const value = it.options.getInteger(name);
        if (value !== null) voice[AUDIO_KEYS[name]] = name === 'bitrate' ? value * 1000 : value;
      }
      await it.deferReply({ flags: MessageFlags.Ephemeral });
      const answer = await askLogger(voice);
      if (Object.keys(voice).length) log(`command: audio ${JSON.stringify(voice)} by ${it.user.tag}`);
      if (!answer) {
        return it.editReply(`ロガーから返事がありません（部屋 \`${room.name}\` にロガーがいない、または音声が止まっている）。`
          + (loggerConfig ? `\n前回の値:\n${audioText(loggerConfig)}` : ''));
      }
      return it.editReply(`${Object.keys(voice).length ? '変えました。' : 'いまの設定です。'}\n${audioText(answer)}`);
    }
    if (sub === 'leave') {
      wantChannel = null;
      saveState({ channelId: null, room: room.name });
      leave();
      log(`command: leave by ${it.user.tag}`);
      return reply('ボイスチャンネルから出ました。部屋とのつながりはそのままです。');
    }
    // join
    const roomName = it.options.getString('room');
    if (roomName !== null && !ROOM_NAME.test(roomName)) return reply('部屋の名前は英数字・`-`・`_`だけにしてください。');
    let channelId = it.options.getChannel('channel')?.id;
    if (!channelId) {
      const member = await it.guild.members.fetch(it.user.id);
      channelId = member.voice.channelId;
      if (!channelId) return reply('ボイスチャンネルに入ってから呼ぶか、`channel`で指定してください。');
    }
    await it.deferReply({ flags: MessageFlags.Ephemeral });
    if (roomName && roomName !== room.name) {
      // the server only accepts registered rooms (400 otherwise): try it, fall back if it fails
      const prev = room.name;
      room.switchTo(roomName);
      for (let i = 0; i < 30 && !room.connected; i++) await new Promise((r) => setTimeout(r, 100));
      if (!room.connected) {
        room.switchTo(prev);
        return it.editReply(`部屋 \`${roomName}\` に入れませんでした（サーバーに登録されていない名前かもしれません）。\`${prev}\` のままです。`);
      }
    }
    wantChannel = channelId;
    saveState({ channelId, room: room.name });
    log(`command: join ${channelId} room ${room.name} by ${it.user.tag}`);
    try {
      await join(channelId);
      await entersState(connection, VoiceConnectionStatus.Ready, 15000);
      await it.editReply(`つなぎました。\n${statusText()}`);
    } catch (e) {
      await it.editReply(`ボイスチャンネルに入れませんでした（${e.message}）。\n${statusText()}`);
    }
  }

  client.on(Events.InteractionCreate, (it) => {
    if (!it.isChatInputCommand() || it.commandName !== 'ecologger' || it.guildId !== GUILD_ID) return;
    onCommand(it).catch((e) => {
      log('command failed:', e.message);
      if (!it.replied && !it.deferred) it.reply({ content: `失敗しました（${e.message}）`, flags: MessageFlags.Ephemeral }).catch(() => {});
    });
  });

  client.once(Events.ClientReady, async (c) => {
    log(`discord: logged in as ${c.user.tag}`);
    try {
      const guild = await client.guilds.fetch(GUILD_ID);
      await guild.commands.set([command.toJSON()]);  // guild commands show up at once
      log('discord: /ecologger registered');
    } catch (e) { log('command registration failed:', e.message); }
    if (wantChannel) join(wantChannel).catch((e) => log('join failed:', e.message));
    else log('discord voice: not joining (left by command)');
  });
  client.login(process.env.DISCORD_TOKEN);
}

// Where the last /ecologger command left us: {channelId, room}.
function loadState() {
  try { return JSON.parse(fs.readFileSync(STATE_FILE, 'utf8')); } catch { return {}; }
}
function saveState(s) {
  try { fs.writeFileSync(STATE_FILE, JSON.stringify(s) + '\n'); } catch (e) { log('state not saved:', e.message); }
}

if (DRY_RUN) dryRun(); else discord();
