#!/bin/bash

# DC-5/DC-6向けに、AutosportLabs公式スクリプト(racecapture_video_data_livestreaming
# リポジトリのracecapture_streaming_install.sh)をUbuntu Server 24.04(noble)向けに
# 最小限だけ修正した版。Intel実機(EliteDesk 800 G3等)向け。
# 修正点は3箇所のみ、いずれもUbuntu 24.04でのパッケージ変更に追随するためで、
# Intel/AMDの違いによるものではない（詳細はtask_dashcam_breakdown.md DC-4-2/DC-5-2参照）。
#   1. libegl1-mesa -> libegl1 (24.04でのパッケージ名変更)
#   2. gconf2 を削除 (24.04に存在しないGNOME2時代のパッケージ、依存関係には無関係と確認済み)
#   3. gstreamer1.0-vaapi gstreamer1.0-tools を追加 (公式スクリプトに元々欠けていた項目)
# 元スクリプトのIntel向け記述(intel-media-va-driver-non-free)はそのまま維持している。

# install dependencies
echo "Installing additional packages"
sudo apt-get -qq update
sudo apt-get -y -qq install mesa-utils libegl1 mtdev-tools intel-media-va-driver-non-free curl v4l-utils tk gstreamer1.0-plugins-bad gstreamer1.0-libav gstreamer1.0-vaapi gstreamer1.0-tools gnome-shell-extensions ratpoison jq

RC_APP_ID=`curl -s 'https://podium.live/api/v1/applications.json?expand=1' | jq -r '.applications[] | select(.name == "racecaptureapp") | .id'`
RC_APP_URL=`curl -s "https://podium.live/api/v1/applications/$RC_APP_ID/latest.json?expand=1&platform=linux" | jq -r .release.url`
RC_APP_FILENAME=`basename "$RC_APP_URL" | sed 's/\?.*//'`
VSTREAMER_APP_ID=`curl -s 'https://podium.live/api/v1/applications.json?expand=1' | jq -r '.applications[] | select(.name == "video-streamer") | .id'`
VSTREAMER_URL=`curl -s "https://podium.live/api/v1/applications/$VSTREAMER_APP_ID/latest.json?expand=1&platform=linux" | jq -r .release.url`
VSTREAMER_FILENAME=`basename "$VSTREAMER_URL" | sed 's/\?.*//'`

# enable access to RaceCapture USB and other /dev files
echo "Enabling access to system devices"
sudo adduser $USER dialout >/dev/null 2>&1
sudo adduser $USER render >/dev/null 2>&1
sudo adduser $USER video >/dev/null 2>&1
sudo adduser $USER input >/dev/null 2>&1
sudo echo "ATTRS{idVendor}==16d0, ATTRS{idProduct}==07f1, MODE=0666" | sudo tee /etc/udev/rules.d/70-autosportlabs.racecapture.rules >/dev/null 2>&1

# The commands below assume we're in $HOME so just change directories now
cd $HOME

# Download the RC app installer
echo "Installing RC App '$RC_APP_FILENAME'"
wget -q --progress=bar --show-progress "$RC_APP_URL" -O "$RC_APP_FILENAME"

# install RC app, with cleanup
sudo dpkg -i $RC_APP_FILENAME && rm $RC_APP_FILENAME

echo "Installing Video Streamer App '$VSTREAMER_FILENAME'"
wget -q --progress=bar --show-progress "$VSTREAMER_URL" -O "$VSTREAMER_FILENAME"

# install video-streamer, with cleanup
sudo dpkg -i $VSTREAMER_FILENAME && rm $VSTREAMER_FILENAME


if [ ! -f ~/Desktop/video-config.ini ] ; then
  echo "Adding default video-config.ini file for configuring streaming and recording settings"
  cat > ~/Desktop/video-config.ini <<'EOF'
[capture]
audio_device=1

[local_recording]
video_dir=$HOME/Videos
segment_length_sec=60

[streaming]
streaming_url=rtmp://a.rtmp.youtube.com/live2/<streaming key>
EOF
fi

echo "Configuring auto-start for racecapture and streaming"
cat > ~/.ratpoisonrc <<'EOF'
## Disable the message in the upper right
set startupmessage 0
## Force the cursor to the lower right when RC starts up
addhook newwindow banish

## Make it so that 'ctrl-t q' quits
bind q exec bash -c "killall -w -s SIGINT video-streamer; ratpoison -c quit"

## Set the cursor to the left pointer
exec xsetroot -cursor_name left_ptr

## Disable screen saver/blanking/etc
exec gsettings set org.gnome.desktop.session idle-delay 0
exec gsettings set org.gnome.settings-daemon.plugins.power idle-dim false
exec gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing'
exec xset s off
exec xset s noblank
exec xset -dpms

## Start RC APP
exec /bin/bash -c "mkdir -p ~/logs; cd /opt/racecapture && ./race_capture --size=1920x1080 >> ~/logs/racecapture_app_$(date +"%Y-%m-%dT%T.%3N").log 2>&1" &

## Start the video capture/streaming
exec /bin/bash -c 'cd /opt/video-streamer && ./start-video-streamer.sh -w 1 2>&1' &
EOF

sudo sh -c "cat > /usr/share/xsessions/racecapture.desktop <<'EOF'
[Desktop Entry]
Name=RaceCapture video+data streamer
Comment=This session logs you into Ratpoison
Exec=/usr/bin/ratpoison
TryExec=/usr/bin/ratpoison
Icon=
Type=Application
X-Ubuntu-Gettext-Domain=ratpoison-session
EOF
"

echo "Changing your window manager to single app mode"
sudo sed -i "s/Session=.*/Session=racecapture/g" /var/lib/AccountsService/users/$USER
