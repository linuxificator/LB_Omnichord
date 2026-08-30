#!/usr/bin/env bash
set -euo pipefail

readonly package=org.linuxificator.lb_omnichord
readonly evidence_dir=android-audio-capture
readonly status_file="$evidence_dir/lb-android-smoke.status"
readonly log_file="$evidence_dir/lb-android.log"
mkdir -p "$evidence_dir"

capture_diagnostics() {
  adb logcat -d > "$log_file" 2>/dev/null || true
  adb exec-out run-as "$package" cat \
    files/lb-android-package-smoke.status > "$status_file" 2>/dev/null || true
}
trap capture_diagnostics EXIT

mapfile -t apks < <(find android-package -type f -name '*.apk' -print)
if [[ ${#apks[@]} -ne 1 ]]; then
  echo "Expected exactly one x86_64 Android package, found ${#apks[@]}" >&2
  exit 1
fi
readonly apk=${apks[0]}
test -s "$apk"

adb uninstall "$package" >/dev/null 2>&1 || true
adb install "$apk"
adb shell run-as "$package" mkdir -p files

# python-for-Android extracts its private Python/Qt payload on first launch.
# Warm that install before arming AMY's eight-second Oboe capture so unpacking
# time cannot consume the capture window before the frontend sends notes. A
# Qt/JNI startup can occasionally lose the race with that first extraction;
# retry only this unmeasured warm-up, while leaving the measured launch and all
# of its QML/audio assertions single-shot.
warmup_ready=0
for warmup_attempt in {1..3}; do
  adb logcat -c
  adb shell monkey -p "$package" 1
  for warmup_poll in {1..120}; do
    if adb logcat -d -s 'python:I' '*:S' \
        > /tmp/lb-android-warmup.log 2>/dev/null && \
        grep -q 'QPA platform: android' /tmp/lb-android-warmup.log; then
      warmup_ready=1
      break 2
    fi
    # Give ActivityManager two seconds to register the launched process, then
    # stop waiting immediately if Qt died so the extracted payload can be
    # retried. The :amy service has a different process name and cannot make
    # this exact pidof check pass.
    if (( warmup_poll >= 4 )) && \
        ! adb shell pidof "$package" >/dev/null 2>&1; then
      echo "Warm-up attempt $warmup_attempt exited before Qt became ready" >&2
      break
    fi
    sleep 0.5
  done
  adb shell am force-stop "$package"
  sleep 1
done
test "$warmup_ready" -eq 1
! grep -q 'Traceback (most recent call last)' /tmp/lb-android-warmup.log
adb shell am force-stop "$package"

adb shell run-as "$package" touch files/lb-android-package-smoke.enable
adb shell run-as "$package" touch files/amy-audio-capture.enable
adb logcat -c
adb shell monkey -p "$package" 1

for _ in {1..120}; do
  if adb exec-out run-as "$package" cat \
      files/lb-android-package-smoke.status \
      > "$status_file" 2>/dev/null && \
      grep -q 'event-loop-exited' "$status_file"; then
    break
  fi
  sleep 0.5
done
capture_diagnostics
cat "$status_file"
grep -E 'AmyAndroid|AmyAudioCapture|AMY backend|QPA platform|Traceback' \
  "$log_file" || true
for checkpoint in \
  android-runtime-configured \
  qml-root-ready \
  initial-state-sent \
  smoke-audio-levels-full \
  qml-chord-press-observed \
  active-chord-visible \
  qml-chord-tap-released \
  qml-chord-hold-promoted \
  qml-chord-hold-released \
  event-loop-exited; do
  grep -q "$checkpoint" "$status_file"
done
grep -q 'AMY/Oboe started: .*336 oscs, 11 buses' "$log_file"
grep -q 'Audio capture armed: 384000 frames, 48000 Hz, 2 channels' "$log_file"
grep -q 'AMY output route: deviceId=' "$log_file"
grep -q 'QPA platform: android' "$log_file"
grep -q 'AMY backend: external socket .*amy.sock' "$log_file"
! grep -q 'Traceback (most recent call last)' "$log_file"

for _ in {1..60}; do
  if adb shell run-as "$package" test -s files/amy-audio-levels.txt; then
    break
  fi
  sleep 0.5
done
adb exec-out run-as "$package" cat files/amy-render.wav \
  > "$evidence_dir/amy-render.wav"
adb exec-out run-as "$package" cat files/amy-oboe.wav \
  > "$evidence_dir/amy-oboe.wav"
adb exec-out run-as "$package" cat files/amy-audio-levels.txt \
  > "$evidence_dir/amy-audio-levels.txt"
test -s "$evidence_dir/amy-render.wav"
test -s "$evidence_dir/amy-oboe.wav"
test -s "$evidence_dir/amy-audio-levels.txt"
cat "$evidence_dir/amy-audio-levels.txt"
python3 "$RUNNER_TEMP/amy-lb/tests/check_android_audio_capture.py" \
  "$evidence_dir/amy-render.wav" \
  "$evidence_dir/amy-oboe.wav" \
  --min-peak-dbfs -26.0

trap - EXIT
