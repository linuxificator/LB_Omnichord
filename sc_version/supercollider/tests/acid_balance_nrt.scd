/* Render the four owned acid voices at three bass registers for calibration. */
(
var directory = thisProcess.nowExecutingPath.dirname.dirname;
var output = "OMNICHORD_SC_ACID_BALANCE_OUTPUT".getenv ?
    (Platform.defaultTempDir +/+ "lb-omnichord-acid-balance.wav");
var oscFile = output ++ ".osc";
var defDirectory = output ++ ".defs";
var names = [\omniAcid303, \omniAcidOto, \omniAcidMoog, \omniAcidWarsaw];
var programs = [
    "sc.omni.acid303", "sc.omni.acidOto",
    "sc.omni.acidMoog", "sc.omni.acidWarsaw"
];
var frequencies = [55.0, 110.0, 220.0];
var score = List.new;
var options = ServerOptions.new;
var segmentSeconds = 0.8;
var noteSeconds = 0.5;
var index = 0;
var endSeconds;

(directory +/+ "acid_voices.scd").load;
SynthDef(\omniAcidBalanceOutput, { |in=16, out=0|
    Out.ar(out, Limiter.ar(In.ar(in, 2), 0.95, 0.005));
}).add;
File.mkdir(defDirectory);
names.do { |name| SynthDescLib.global.at(name).def.writeDefFile(defDirectory) };
SynthDescLib.global.at(\omniAcidBalanceOutput).def.writeDefFile(defDirectory);
score.add([0.0, [\d_loadDir, defDirectory]]);
score.add([0.0, [\c_set, 0, 1.0]]);
names.do { |name, programIndex|
    frequencies.do { |frequency|
        var start = 0.05 + (index * segmentSeconds);
        var sourceId = 1000 + index;
        var outputId = 2000 + index;
        score.add([start, [
            \s_new, name, sourceId, 0, 0,
            \out, 16, \freqTargetHz, frequency, \velocity, 0.7,
            \calibrationGain, ~omniAcidPlaybackGain.value(programs[programIndex]),
            \pitchBendBus, 0
        ]]);
        score.add([start + 0.001, [
            \s_new, \omniAcidBalanceOutput, outputId, 1, 0,
            \in, 16, \out, 0
        ]]);
        score.add([start + noteSeconds, [\n_set, sourceId, \gate, 0]]);
        score.add([start + 0.74, [\n_free, outputId]]);
        index = index + 1;
    };
};
endSeconds = 0.1 + (index * segmentSeconds);
score.add([endSeconds, [\c_set, 0, 0]]);
options.numInputBusChannels = 0;
options.numOutputBusChannels = 2;
options.sampleRate = 48000;
options.blockSize = 64;
options.maxNodes = 256;
options.memSize = 65536;

Score.recordNRT(
    score.asArray.sort { |left, right| left[0] < right[0] },
    oscFile,
    output,
    sampleRate: 48000,
    headerFormat: "WAV",
    sampleFormat: "float",
    options: options,
    duration: endSeconds,
    action: {
        ("LB_OMNICHORD_ACID_BALANCE_NRT_OK output=" ++ output).postln;
        0.exit;
    }
);
)
