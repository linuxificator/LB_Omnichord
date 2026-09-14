/* Render the production mono/stereo sample players from synthetic fixtures. */
(
var directory = thisProcess.nowExecutingPath.dirname.dirname;
var output = "OMNICHORD_SC_SAMPLE_NRT_OUTPUT".getenv;
var mono = "OMNICHORD_SC_SAMPLE_NRT_MONO".getenv;
var stereo = "OMNICHORD_SC_SAMPLE_NRT_STEREO".getenv;
var oscFile = output ++ ".osc";
var defDirectory = output ++ ".defs";
var score = List.new;
var options = ServerOptions.new;

if(output.isNil or: { mono.isNil } or: { stereo.isNil }) {
    Error("sample NRT fixture paths are required").throw;
};
(directory +/+ "sample_loader.scd").load;
File.mkdir(defDirectory);
SynthDescLib.global.at(\omniSampleMono).def.writeDefFile(defDirectory);
SynthDescLib.global.at(\omniSampleStereo).def.writeDefFile(defDirectory);

score.add([0.0, [\d_loadDir, defDirectory]]);
score.add([0.01, [\b_allocRead, 0, mono]]);
score.add([0.01, [\b_allocRead, 1, stereo]]);
score.add([0.02, [\c_set, 20, 1.0]]);
score.add([0.10, [
    \s_new, \omniSampleMono, 1000, 0, 0,
    \out, 0, \buffer, 0, \rate, 1, \velocity, 0.8, \gain, 0.5,
    \attack, 0.001, \release, 0.04, \pitchBendBus, 20
]]);
score.add([0.30, [\n_set, 1000, \gate, 0]]);
score.add([0.60, [
    \s_new, \omniSampleStereo, 1001, 0, 0,
    \out, 0, \buffer, 1, \rate, 1, \velocity, 0.8, \gain, 0.5,
    \attack, 0.001, \release, 0.04, \pitchBendBus, 20
]]);
score.add([0.80, [\n_set, 1001, \gate, 0]]);
score.add([1.10, [\b_free, 0]]);
score.add([1.10, [\b_free, 1]]);
score.add([1.15, [\c_set, 0, 0]]);

options.numInputBusChannels = 0;
options.numOutputBusChannels = 2;
options.sampleRate = 48000;
options.blockSize = 64;
options.maxNodes = 128;
options.memSize = 32768;

Score.recordNRT(
    score.asArray.sort { |left, right| left[0] < right[0] },
    oscFile,
    output,
    sampleRate: 48000,
    headerFormat: "WAV",
    sampleFormat: "int16",
    options: options,
    duration: 1.2,
    action: {
        ("LB_OMNICHORD_SAMPLE_NRT_OK output=" ++ output).postln;
        0.exit;
    }
);
)
