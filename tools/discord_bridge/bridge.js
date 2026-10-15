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
// DRY_RUN=tone|listen skips Discord: "tone" sends a 3 s test tone into the room,
// "listen" counts the mix packets it gets (to test the server side without a token).
'use strict';

const OpusScript = require('opusscript');
const WebSocket = require('ws');

const ECORUN_URL = process.env.ECORUN_URL || 'ws://127.0.0.1:3000';
const ROOM = process.env.ECORUN_ROOM || 'home-test';
const DRY_RUN = process.env.DRY_RUN || '';

const ROOM_RATE = 8000;          // server format (src/audio.rs)
const SEND_FRAME = 480;          // 60 ms at 8 kHz, the server's frame
const MIX_FORMAT = { sample_rate: 8000, channels: 1, frame_ms: 120 };  // logger mix (src/mixer.rs)
const DISCORD_RATE = 48000;
const RATIO = DISCORD_RATE / ROOM_RATE;  // 6
const PTT_OFF_MS = 500;          // release ptt this long after the last Discord audio
const MAX_BUFFER = SEND_FRAME * 4;

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

const toInt16 = (buf) => new Int16Array(buf.buffer, buf.byteOffset, buf.length / 2);
const clip = (v) => Math.max(-32768, Math.min(32767, Math.round(v)));

// ---- the server room -----------------------------------------------------
class Room {
  constructor(onMix) {
    this.onMix = onMix;
    this.ws = null;
    this.ptt = false;
    this.connect();
  }
  connect() {
    const url = `${ECORUN_URL}/ws/audio/${encodeURIComponent(ROOM)}`;
    const ws = this.ws = new WebSocket(url);
    ws.on('open', () => {
      log(`room ${ROOM}: connected`);
      this.ptt = false;
      ws.send(JSON.stringify({ type: 'hello', client_id: 'discord-bridge', protocol: 1, audio_formats: [MIX_FORMAT] }));
    });
    ws.on('message', (data, binary) => { if (binary) this.onMix(data); });
    ws.on('close', () => { log(`room ${ROOM}: closed, reconnecting`); setTimeout(() => this.connect(), 2000); });
    ws.on('error', (e) => log(`room ${ROOM}: ${e.message}`));
  }
  setPtt(active) {
    if (active === this.ptt || this.ws.readyState !== WebSocket.OPEN) return;
    this.ptt = active;
    this.ws.send(JSON.stringify({ type: 'audio.ptt', active }));
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
  drop(userId) { this.sources.delete(userId); }
}

// ---- dry runs (no Discord) ------------------------------------------------
function dryRun() {
  if (DRY_RUN === 'listen') {
    const decoder = new OpusScript(ROOM_RATE, 1);
    let packets = 0, bytes = 0, peak = 0;
    new Room((p) => {
      packets++; bytes += p.length;
      const pcm = toInt16(decoder.decode(p));
      for (const v of pcm) peak = Math.max(peak, Math.abs(v));
    });
    setInterval(() => { log(`mix received: ${packets} packets, ${bytes} bytes, peak ${peak}`); peak = 0; }, 2000);
    return;
  }
  // tone: 440 Hz as if a Discord user spoke for 3 s, fed through the real 48 kHz path
  const room = new Room(() => {});
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
  const { Client, GatewayIntentBits, Events } = require('discord.js');
  const {
    joinVoiceChannel, createAudioPlayer, createAudioResource, StreamType, NoSubscriberBehavior,
    AudioPlayerStatus, EndBehaviorType, VoiceConnectionStatus, entersState,
  } = require('@discordjs/voice');
  const { PassThrough } = require('stream');

  const client = new Client({ intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildVoiceStates] });
  const decoder8k = new OpusScript(ROOM_RATE, 1);
  const up = new Upsampler();
  const player = createAudioPlayer({ behaviors: { noSubscriber: NoSubscriberBehavior.Play, maxMissedFrames: 50 } });
  let stream = null;
  player.on(AudioPlayerStatus.Idle, () => { stream = null; });
  player.on('error', (e) => { log('player:', e.message); stream = null; });

  // room -> Discord: a new raw-PCM resource whenever the room starts talking again
  const room = new Room((packet) => {
    let mono;
    try { mono = toInt16(decoder8k.decode(packet)); } catch { return; }
    if (!stream) {
      stream = new PassThrough();
      player.play(createAudioResource(stream, { inputType: StreamType.Raw }));
    }
    const pcm = up.push(mono);
    stream.write(Buffer.from(pcm.buffer));
  });
  const down = new DiscordToRoom(room);

  async function join() {
    const guild = await client.guilds.fetch(process.env.DISCORD_GUILD_ID);
    const connection = joinVoiceChannel({
      guildId: guild.id, channelId: process.env.DISCORD_CHANNEL_ID,
      adapterCreator: guild.voiceAdapterCreator, selfDeaf: false, selfMute: false,
    });
    connection.subscribe(player);
    connection.on(VoiceConnectionStatus.Ready, () => log('discord voice: ready'));
    connection.on(VoiceConnectionStatus.Disconnected, async () => {
      try {
        await Promise.race([
          entersState(connection, VoiceConnectionStatus.Signalling, 5000),
          entersState(connection, VoiceConnectionStatus.Connecting, 5000),
        ]);
      } catch {
        log('discord voice: lost, rejoining');
        connection.destroy();
        setTimeout(join, 3000);
      }
    });
    // Discord -> room
    connection.receiver.speaking.on('start', (userId) => {
      if (connection.receiver.subscriptions.has(userId)) return;
      const opus = connection.receiver.subscribe(userId, { end: { behavior: EndBehaviorType.AfterSilence, duration: 400 } });
      opus.on('data', (packet) => down.pushOpus(userId, packet));
      opus.on('end', () => down.drop(userId));
      opus.on('error', (e) => log(`receive ${userId}:`, e.message));
    });
  }

  client.once(Events.ClientReady, (c) => { log(`discord: logged in as ${c.user.tag}`); join().catch((e) => log('join failed:', e.message)); });
  client.login(process.env.DISCORD_TOKEN);
}

if (DRY_RUN) dryRun(); else discord();
