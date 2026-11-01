#!/bin/bash
# Read-only audio + power_supply inventory for the Dragonfly G4, run from an Ubuntu live USB:
#   sudo bash collect-audio-power.sh /media/<stick>/audio-power
# Connect the AC adapter before running. Nothing is written outside OUTDIR.
set -u
OUT=${1:-./audio-power-$(date +%Y%m%d%H%M%S)}
mkdir -p "$OUT"; cd "$OUT" || exit 1
run() { local f=$1; shift; echo "== $*" >"$f"; "$@" >>"$f" 2>&1; }

run cards.txt cat /proc/asound/cards
run pcm.txt cat /proc/asound/pcm
run amixer-contents.txt amixer -c 0 contents
run amixer-scontrols.txt amixer -c 0 scontrols
run aplay-l.txt aplay -l
run arecord-l.txt arecord -l
run jacks.txt sh -c 'grep -H "" /proc/bus/input/devices | grep -E "Name=.*(Headphone|Mic|HDMI)"'
run sof-dmesg.txt sh -c 'dmesg | grep -iE "sof|hda|alc245|cs35l41|snd"'
run ucm.txt sh -c 'alsaucm -c sof-hda-dsp list _verbs; alsaucm -c sof-hda-dsp list _devices/HiFi'
run power-supply.txt sh -c 'for d in /sys/class/power_supply/*; do echo "== $d -> $(readlink -f $d)"; for f in type online status capacity present scope usb_type; do [ -e $d/$f ] && echo "$f=$(cat $d/$f)"; done; done'
sync
echo "done: $(pwd) ($(find . -type f -size +0 | wc -l) non-empty files)"
