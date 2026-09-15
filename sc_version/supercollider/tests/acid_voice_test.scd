/* Compile and inspect all native acid voices without opening audio. */
(
var directory = thisProcess.nowExecutingPath.dirname.dirname;
var names = [\omniAcid303, \omniAcidOto, \omniAcidMoog, \omniAcidWarsaw];
var required = [
    \out, \freqTargetHz, \gate, \velocity, \gain, \calibrationGain, \waveform,
    \cutoffHz, \resonanceNormalized, \envOctaves, \filterDecaySeconds,
    \slideSeconds, \slideEnabled, \t_attack, \t_filter, \t_accent,
    \accentAmount, \pitchBendBus
];
var failed = false;

~omniPreparedArgs = { [] };
(directory +/+ "acid_voices.scd").load;
names.do { |name|
    var description = SynthDescLib.global.at(name);
    if(description.isNil) {
        failed = true;
        ("ACID_VOICE_MISSING " ++ name).postln;
    } {
        var controls = description.controls.collect(_.name);
        required.do { |control|
            if(controls.includes(control).not) {
                failed = true;
                ("ACID_CONTROL_MISSING " ++ name ++ " " ++ control).postln;
            };
        };
    };
};
if(~omniAcidProgramName.value("sc.omni.acidMoog") != \omniAcidMoog) {
    failed = true;
    "ACID_PROGRAM_MAP_FAILED".postln;
};
if((~omniAcidPlaybackGain.value("sc.omni.acidOto") - 0.127327).abs > 0.000001) {
    failed = true;
    "ACID_PLAYBACK_GAIN_FAILED".postln;
};
if(failed) { 1.exit } {
    "ACID_VOICE_TEST_OK".postln;
    0.exit
};
)
