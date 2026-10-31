#!/usr/bin/env bash
# Reels: frames/<ad>_N.png kareleri → 1080x1920 H.264, kareler arası xfade (slideleft, 0,35 sn), sessiz ses kanalı
set -e
D=2.6; T=0.35
mk(){ # $1 = kare öneki, $2 = çıktı
  n=$(ls frames/$1_*.png | wc -l); in=(); f=""; prev="0:v"; off=0
  for i in $(seq 0 $((n-1))); do in+=(-loop 1 -t $D -i frames/$1_$i.png); done
  for i in $(seq 1 $((n-1))); do
    off=$(echo "$i*($D-$T)" | bc -l); f+="[$prev][$i:v]xfade=transition=slideleft:duration=$T:offset=$off[v$i];"; prev="v$i"
  done
  f+="[$prev]format=yuv420p,fps=30[out]"
  ffmpeg -y -loglevel error "${in[@]}" -f lavfi -i anullsrc=r=44100:cl=stereo -filter_complex "$f" \
    -map "[out]" -map $n:a -c:v libx264 -preset slow -crf 20 -profile:v high -c:a aac -b:a 128k -shortest -movflags +faststart "$2"
}
mk r1 r1_1111.mp4
mk r2 r2_sektorler.mp4
