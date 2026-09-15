/* Render the ordered parallel production topology through Supernova NRT. */
(
var output = "OMNICHORD_SC_SUPERNOVA_NRT_OUTPUT".getenv;
var directory = thisProcess.nowExecutingPath.dirname.dirname;
var oscFile;
var defDirectory;
var score = List.new;
var options = ServerOptions.new;

if(output.isNil) { Error("Supernova NRT output path is required").throw };
Server.program = "OMNICHORD_SC_NRT_PROGRAM".getenv ? "supernova";
oscFile = output ++ ".osc";
defDirectory = output ++ ".defs";

SynthDef(\omniParallelTestSource, { |out=16, invalid=0|
    var signal = Select.ar(invalid, [SinOsc.ar(220) * 0.1, DC.ar(0) / DC.ar(0)]);
    Out.ar(out, signal ! 2);
}).add;
(directory +/+ "core_synthdefs.scd").load;
File.mkdir(defDirectory);
[\omniParallelTestSource, \omniVoiceOutput, \omniBusStrip,
    \omniMasterOutput].do {
    |name| SynthDescLib.global.at(name).def.writeDefFile(defDirectory)
};

score.add([0.0, [\d_loadDir, defDirectory]]);
score.add([0.01, [\p_new, 10, 0, 0]]);
score.add([0.01, [\p_new, 20, 3, 10]]);
score.add([0.01, [\g_new, 30, 3, 20]]);
score.add([0.01, [\g_new, 11, 1, 10]]);
score.add([0.01, [\g_new, 12, 1, 10]]);
score.add([0.02, [\s_new, \omniParallelTestSource, 100, 1, 11,
    \out, 16]]);
score.add([0.02, [\s_new, \omniVoiceOutput, 101, 3, 100,
    \in, 16, \out, 20]]);
score.add([0.02, [\s_new, \omniParallelTestSource, 102, 1, 12,
    \out, 18, \invalid, 1]]);
score.add([0.02, [\s_new, \omniVoiceOutput, 103, 3, 102,
    \in, 18, \out, 20]]);
score.add([0.02, [\s_new, \omniBusStrip, 104, 1, 20,
    \in, 20, \out, 22, \roomOut, 24, \roomSend, 0]]);
score.add([0.02, [\s_new, \omniMasterOutput, 105, 1, 30,
    \in, 22, \out, 0]]);
score.add([0.30, [\n_free, 11]]);
score.add([0.30, [\n_free, 12]]);
score.add([0.35, [\c_set, 0, 0]]);

options.numInputBusChannels = 0;
options.numOutputBusChannels = 2;
options.sampleRate = 48000;
options.blockSize = 64;
options.maxNodes = 128;

Score.recordNRT(
    score.asArray,
    oscFile,
    output,
    sampleRate: 48000,
    headerFormat: "WAV",
    sampleFormat: "float",
    options: options,
    duration: 0.4,
    action: {
        ("LB_OMNICHORD_SUPERNOVA_NRT_OK output=" ++ output).postln;
        0.exit;
    }
);
)
