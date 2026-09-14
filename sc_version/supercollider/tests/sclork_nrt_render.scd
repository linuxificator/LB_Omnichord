/* Render one bounded segment per SCLOrk program without opening an audio device. */
(
var directory = thisProcess.nowExecutingPath.dirname.dirname;
var output = "OMNICHORD_SC_NRT_OUTPUT".getenv ?
    (Platform.defaultTempDir +/+ "lb-omnichord-sclork-audit.wav");
var oscFile = output ++ ".osc";
var defDirectory = output ++ ".defs";
var catalog = (directory +/+ "sclork-programs.json").parseJSONFile;
var jsonAt = { |object, key| object[key.asString] ? object[key.asSymbol] };
var allPrograms = jsonAt.value(catalog, "programs");
var startIndex = ("OMNICHORD_SC_NRT_START".getenv ? "0").asInteger;
var requestedCount = ("OMNICHORD_SC_NRT_COUNT".getenv ? allPrograms.size.asString).asInteger;
var endIndex = (startIndex + requestedCount - 1).min(allPrograms.size - 1);
var programs;
var score = List.new;
var options = ServerOptions.new;
var segmentSeconds = 0.75;
var noteSeconds = 0.42;
var requestedFrequency = "OMNICHORD_SC_NRT_FREQUENCY".getenv;
var rawOutput = ("OMNICHORD_SC_NRT_RAW".getenv ? "0").asInteger == 1;
var endSeconds;

(directory +/+ "sclork_loader.scd").load;
SynthDef(\omniSclorkAuditOutput, { |in=16, out=0, calibration=1|
    Out.ar(out, In.ar(in, 2) * calibration);
}).add;
if((startIndex < 0) or: { startIndex >= allPrograms.size }) {
    Error("invalid SCLOrk NRT start index: " ++ startIndex).throw;
};
if(requestedCount <= 0) {
    Error("invalid SCLOrk NRT count: " ++ requestedCount).throw;
};
programs = allPrograms.copyRange(startIndex, endIndex);
File.mkdir(defDirectory);
programs.do { |program|
    var name = jsonAt.value(program, "native_name").asSymbol;
    var description = SynthDescLib.global.at(name);
    description.def.writeDefFile(defDirectory);
};
SynthDescLib.global.at(\omniSclorkAuditOutput).def.writeDefFile(defDirectory);
score.add([0.0, [\d_loadDir, defDirectory]]);
programs.do { |program, index|
    var name = jsonAt.value(program, "native_name").asSymbol;
    var programId = jsonAt.value(program, "program_id").asString;
    var category = jsonAt.value(program, "category").asString;
    var nodeId = 1000 + index;
    var outputNodeId = 2000 + index;
    var start = 0.05 + (index * segmentSeconds);
    var frequency = if(category == "drums") {
        nil
    } {
        if(requestedFrequency.isNil) {
            [110.0, 440.0, 880.0][(startIndex + index) % 3]
        } {
            requestedFrequency.asFloat
        }
    };
    var args = ~omniSclorkArgs.value(name, 16, frequency, []);
    score.add([start, [\s_new, name, nodeId, 0, 0] ++ args]);
    score.add([start + 0.001, [
        \s_new, \omniSclorkAuditOutput, outputNodeId, 1, 0,
        \in, 16, \out, 0,
        \calibration, if(rawOutput) {
            1.0
        } {
            ~omniSclorkPlaybackGain.value(programId)
        }
    ]]);
    if(~omniSynthHasControl.value(name, \gate)) {
        score.add([start + noteSeconds, [\n_set, nodeId, \gate, 0]]);
    };
    score.add([start + 0.68, [\n_free, nodeId]]);
    score.add([start + 0.70, [\n_free, outputNodeId]]);
};
endSeconds = 0.1 + (programs.size * segmentSeconds);
score.add([endSeconds, [\c_set, 0, 0]]);
options.numInputBusChannels = 0;
options.numOutputBusChannels = 2;
options.sampleRate = 48000;
options.blockSize = 64;
options.maxNodes = 4096;
options.memSize = 262144;

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
        (
            "LB_OMNICHORD_SCLORK_NRT_OK output=" ++ output
            ++ " start=" ++ startIndex ++ " count=" ++ programs.size
        ).postln;
        0.exit;
    }
);
)
