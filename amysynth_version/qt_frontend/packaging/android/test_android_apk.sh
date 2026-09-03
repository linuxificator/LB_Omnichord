#!/usr/bin/env bash
set -euo pipefail

readonly package=org.linuxificator.lb_omnichord
readonly evidence_dir=android-audio-capture
readonly log_file="$evidence_dir/lb-android.log"
readonly sender_log="$evidence_dir/lb-android-external-osc-sender.log"
readonly input_contract_log="$evidence_dir/external-input-contract.log"
mkdir -p "$evidence_dir"
external_sender_pid=""
osc_port=""

capture_diagnostics() {
  adb logcat -d > "$log_file" 2>/dev/null || true
}

cleanup() {
  if [[ -n "$external_sender_pid" ]]; then
    kill -TERM "$external_sender_pid" 2>/dev/null || true
    wait "$external_sender_pid" 2>/dev/null || true
  fi
  if [[ -n "$osc_port" ]]; then
    adb emu redir del "udp:$osc_port" >/dev/null 2>&1 || true
  fi
  adb shell am force-stop "$package" >/dev/null 2>&1 || true
  capture_diagnostics
}
trap cleanup EXIT

mapfile -t apks < <(find android-package -type f -name '*.apk' -print)
if [[ ${#apks[@]} -ne 1 ]]; then
  echo "Expected exactly one x86_64 Android package, found ${#apks[@]}" >&2
  exit 1
fi
readonly apk=${apks[0]}
test -s "$apk"
mapfile -t package_audits < <(find android-package-evidence -type f -name '*.apk.package-audit.json' -print)
mapfile -t qml_evidence < <(find android-package-evidence -type f -name '*.apk.pyside-prune.json' -print)
if [[ ${#package_audits[@]} -ne 1 || ${#qml_evidence[@]} -ne 1 ]]; then
  echo "Expected one Android package audit and one QML prune report" >&2
  exit 1
fi

python3 amysynth_version/qt_frontend/tests/contracts/test_external_input_processes.py \
  > "$input_contract_log" 2>&1

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

readonly osc_config=amysynth_version/qt_frontend/config/amy_config.json
osc_port=$(python3 \
  amysynth_version/qt_frontend/tests/support/external_input_peer.py \
  osc-port --config "$osc_config")
redir_result=$(adb emu redir add "udp:${osc_port}:${osc_port}")
if [[ "$redir_result" != OK* ]]; then
  echo "Could not configure emulator OSC UDP redirection: $redir_result" >&2
  exit 1
fi

adb shell run-as "$package" touch files/amy-audio-capture.enable
adb logcat -c
python3 amysynth_version/qt_frontend/tests/support/external_input_peer.py \
  osc --config "$osc_config" --duration 30 \
  > "$sender_log" 2>&1 &
external_sender_pid=$!
adb shell monkey -p "$package" 1

for _ in {1..120}; do
  adb logcat -d > "$log_file" 2>/dev/null || true
  if grep -q 'Audio capture armed: 384000 frames' "$log_file" && \
      grep -q 'QPA platform: android' "$log_file"; then
    break
  fi
  sleep 0.5
done

# Drive the packaged UI from the adb process. The landscape Pixel 2 viewport
# maps the first C chord key near (250, 800); a swipe with equal endpoints is
# an external long press and exercises both press and release delivery.
adb exec-out screencap -p > "$evidence_dir/omni-before.png"
adb shell input swipe 250 800 250 800 700
sleep 1
adb exec-out screencap -p > "$evidence_dir/omni-after.png"
capture_diagnostics
kill -TERM "$external_sender_pid" 2>/dev/null || true
wait "$external_sender_pid" 2>/dev/null || true
external_sender_pid=""
cat "$sender_log"
grep -q 'osc-external-process-started' "$sender_log"
grep -E 'AmyAndroid|AmyAudioCapture|AMY backend|QPA platform|Traceback' \
  "$log_file" || true
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
  --min-peak-dbfs -26.0 | tee "$evidence_dir/audio-check.log"

python3 amysynth_version/qt_frontend/tests/support/package_evidence.py \
  --platform Android-x86_64 \
  --artifact "$apk" \
  --package-audit "${package_audits[0]}" \
  --qml-imports "${qml_evidence[0]}" \
  --application-log "$log_file" \
  --external-input-contract-log "$input_contract_log" \
  --screenshot "$evidence_dir/omni-before.png" \
  --screenshot "$evidence_dir/omni-after.png" \
  --regression-result success \
  --audio-evidence "$evidence_dir/audio-check.log" \
  --output "$evidence_dir/package-evidence.json"

trap - EXIT
