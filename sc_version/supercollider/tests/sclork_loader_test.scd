/* Evaluate the production loader without booting an audio server. */
(
var directory = thisProcess.nowExecutingPath.dirname.dirname;
var expected = [
    \acidOto3091,
    \pulseRisset,
    \pluck,
    \sawSynth,
    \sosBell,
    \kik3,
    \kickBlocks,
    \waveguideFlute
];
var failed = false;

(directory +/+ "sclork_loader.scd").load;
expected.do { |name|
    var description = SynthDescLib.global.at(name);
    if(description.isNil) {
        failed = true;
        ("SCLORK_LOADER_MISSING " ++ name).postln;
    };
};
if(~omniSclorkProgramName.value("sc.sclork.fmBass") != \fmBass) {
    failed = true;
    "SCLORK_LOADER_PROGRAM_ID_FAILED".postln;
};
if(~omniSclorkProgramName.value("legacy.program").notNil) {
    failed = true;
    "SCLORK_LOADER_LEGACY_ID_FAILED".postln;
};
if(~omniSynthHasControl.value(\fmBass, \freq).not) {
    failed = true;
    "SCLORK_LOADER_CONTROL_FAILED".postln;
};
if(~omniSclorkArgs.value(\everythingRhodes, 0, 440, []).includesEqual(\amp)) {
    failed = true;
    "SCLORK_LOADER_OVERRODE_NATIVE_AMP_FAILED".postln;
};
{
    var controls = ~omniSclorkArgs.value(
        \bassWarsaw,
        0,
        440,
        ["attack_ms", 250, "portamento_ms", 80]
    );
    if(
        (controls[controls.indexOf(\att) + 1] != 0.25)
        or: { controls[controls.indexOf(\slideTime) + 1] != 0.08 }
    ) {
        failed = true;
        "SCLORK_LOADER_NORMALIZED_CONTROLS_FAILED".postln;
    };
}.value;
{
    var controls = ~omniSclorkArgs.value(
        \combs, 0, 440, ["filter_rq", 0.4]
    );
    if(controls[controls.indexOf(\rq) + 1] != 0.4) {
        failed = true;
        "SCLORK_LOADER_FILTER_RQ_FAILED".postln;
    };
}.value;
{
    var controls = ~omniSclorkArgs.value(
        \sosHats, 0, 440, ["bodyRel", "0.06"]
    );
    var bodyRel = controls[controls.indexOf(\bodyRel) + 1];
    if((bodyRel.class != Float) or: { (bodyRel - 0.06).abs > 0.000001 }) {
        failed = true;
        "SCLORK_LOADER_NUMERIC_CONTROL_COERCION_FAILED".postln;
    };
}.value;
if((~omniSclorkPlaybackGain.value("sc.sclork.everythingRhodes") - 0.003854).abs
    > 0.000001) {
    failed = true;
    "SCLORK_LOADER_HOT_PROGRAM_CALIBRATION_FAILED".postln;
};
if((~omniSclorkPlaybackGain.value("sc.sclork.glockenspiel") - 16).abs
    > 0.000001) {
    failed = true;
    "SCLORK_LOADER_QUIET_PROGRAM_CALIBRATION_FAILED".postln;
};
if(failed) { 1.exit } {
    "SCLORK_LOADER_TEST_OK".postln;
    0.exit
};
)
