#!/bin/bash
# usage: capture-ios.sh <udid> <bundle-id> <content-size> <out-prefix> [with-patched]
# Writes <out>-stock.png, <out>-stock-bottom.png (scrolled to the end), the same
# for -patched if asked, and <out>.log with the [inline-baseline] lines.
set -u
UDID=$1; BUNDLE=$2; SIZE=$3; OUT=$4; PATCHED=${5:-}
shot() { sleep 2; xcrun simctl io $UDID screenshot $1 >/dev/null 2>&1; }
down() { rocketsim interact swipe --from 200,780 --to 200,180 --duration 1.2 --udid $UDID >/dev/null 2>&1; }
up() { rocketsim interact swipe --from 200,180 --to 200,780 --duration 1.2 --udid $UDID >/dev/null 2>&1; }
xcrun simctl ui $UDID content_size $SIZE
# Quit both repro apps and go home, so the status bar has no "back to app" link.
xcrun simctl terminate $UDID org.reactjs.native.example.ReproducerApp 2>/dev/null
xcrun simctl terminate $UDID org.reactjs.native.example.InlineBaseline081 2>/dev/null
rocketsim interact button home --udid $UDID >/dev/null 2>&1
sleep 2
xcrun simctl spawn $UDID log stream --style compact --predicate 'eventMessage CONTAINS "[inline-baseline]"' > $OUT.log 2>&1 &
LOGPID=$!
sleep 2
xcrun simctl launch $UDID $BUNDLE >/dev/null
sleep 8
shot $OUT-stock.png
down; shot $OUT-stock-bottom.png
if [ -n "$PATCHED" ]; then
  up; sleep 1
  rocketsim interact tap --label patched --udid $UDID >/dev/null 2>&1 || echo "tap failed"
  sleep 3
  shot $OUT-patched.png
  down; shot $OUT-patched-bottom.png
fi
sleep 1
kill $LOGPID
echo done $OUT
