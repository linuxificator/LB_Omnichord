/* Build every owned core SynthDef without opening an audio server. */
(
var directory = thisProcess.nowExecutingPath.dirname.dirname;
var names = [
    \omniVoice, \omniDrum, \omniVoiceOutput, \omniBusStrip,
    \omniRoom, \omniMasterOutput
];
var failed = false;

(directory +/+ "core_synthdefs.scd").load;
names.do { |name|
    var description = SynthDescLib.global.at(name);
    if(description.isNil) {
        failed = true;
        ("CORE_SYNTHDEF_MISSING " ++ name).postln;
    } {
        try {
            if(description.def.asBytes.isEmpty) {
                failed = true;
                ("CORE_SYNTHDEF_EMPTY " ++ name).postln;
            };
        } { |error|
            failed = true;
            ("CORE_SYNTHDEF_SERIALIZE_FAILED " ++ name ++ " " ++ error).postln;
        };
    };
};
if(failed) { 1.exit } {
    "CORE_SYNTHDEFS_TEST_OK".postln;
    0.exit
};
)
