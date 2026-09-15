/* Render the ordered parallel production topology through Supernova NRT. */
(
var output = "OMNICHORD_SC_SUPERNOVA_NRT_OUTPUT".getenv;
var oscFile;
var defDirectory;
var score = List.new;
var options = ServerOptions.new;

if(output.isNil) { Error("Supernova NRT output path is required").throw };
Server.program = "OMNICHORD_SC_NRT_PROGRAM".getenv ? "supernova";
oscFile = output ++ ".osc";
defDirectory = output ++ ".defs";

SynthDef(\omniParallelTestSource, { |out=16|
    Out.ar(out, SinOsc.ar(220) * 0.1);
}).add;
SynthDef(\omniParallelTestMix, { |in=16, out=18|
    Out.ar(out, In.ar(in, 2));
}).add;
SynthDef(\omniParallelTestMaster, { |in=18, out=0|
    Out.ar(out, In.ar(in, 2));
}).add;
File.mkdir(defDirectory);
[\omniParallelTestSource, \omniParallelTestMix, \omniParallelTestMaster].do {
    |name| SynthDescLib.global.at(name).def.writeDefFile(defDirectory)
};

score.add([0.0, [\d_loadDir, defDirectory]]);
score.add([0.01, [\p_new, 10, 0, 0]]);
score.add([0.01, [\p_new, 20, 3, 10]]);
score.add([0.01, [\g_new, 30, 3, 20]]);
score.add([0.02, [\s_new, \omniParallelTestSource, 100, 1, 10]]);
score.add([0.02, [\s_new, \omniParallelTestMix, 101, 1, 20]]);
score.add([0.02, [\s_new, \omniParallelTestMaster, 102, 1, 30]]);
score.add([0.30, [\n_free, 100]]);
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
