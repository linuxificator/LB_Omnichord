/* Render one bounded segment per SCLOrk program without opening an audio device. */
(
var directory = thisProcess.nowExecutingPath.dirname.dirname;
var output = "OMNICHORD_SC_NRT_OUTPUT".getenv ?
    (Platform.defaultTempDir +/+ "lb-omnichord-sclork-audit.wav");
var oscFile = output ++ ".osc";
var defDirectory = output.dirname +/+ "sclork-defs";
var catalog = (directory +/+ "sclork-programs.json").parseJSONFile;
var jsonAt = { |object, key| object[key.asString] ? object[key.asSymbol] };
var programs = jsonAt.value(catalog, "programs");
var score = List.new;
var options = ServerOptions.new;
var segmentSeconds = 0.75;
var noteSeconds = 0.42;
var endSeconds;

(directory +/+ "sclork_loader.scd").load;
File.mkdir(defDirectory);
programs.do { |program|
    var name = jsonAt.value(program, "native_name").asSymbol;
    var description = SynthDescLib.global.at(name);
    description.def.writeDefFile(defDirectory);
};
score.add([0.0, [\d_loadDir, defDirectory]]);
programs.do { |program, index|
    var name = jsonAt.value(program, "native_name").asSymbol;
    var nodeId = 1000 + index;
    var start = 0.05 + (index * segmentSeconds);
    var frequency = [110.0, 440.0, 880.0][index % 3];
    var args = ~omniSclorkArgs.value(name, 0, frequency, []);
    score.add([start, [\s_new, name, nodeId, 0, 0] ++ args]);
    if(~omniSynthHasControl.value(name, \gate)) {
        score.add([start + noteSeconds, [\n_set, nodeId, \gate, 0]]);
    };
    score.add([start + 0.68, [\n_free, nodeId]]);
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
    sampleFormat: "int16",
    options: options,
    duration: endSeconds,
    action: {
        ("LB_OMNICHORD_SCLORK_NRT_OK output=" ++ output).postln;
        0.exit;
    }
);
)
