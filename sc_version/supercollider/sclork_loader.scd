/* Load the immutable upstream inventory and LB's minimal routing adapters. */
(
var directory = thisProcess.nowExecutingPath.dirname;
var sourceRoot = directory +/+ "vendor/SCLOrkSynths/SynthDefs";
var adapterRoot = directory +/+ "adapters";
var sourceFiles = List.new;
var playbackProfile = (directory +/+ "sclork-playback.json").parseJSONFile;
var playbackPrograms = playbackProfile["programs"] ? playbackProfile[\programs];

PathName(sourceRoot).folders.do { |folder|
    folder.files.do { |file|
        if(file.extension == "scd") { sourceFiles.add(file) };
    };
};
sourceFiles.sort { |a, b| a.fullPath < b.fullPath }.do { |file|
    file.fullPath.load;
};
PathName(adapterRoot).files
    .select { |file| file.extension == "scd" }
    .sort { |a, b| a.fullPath < b.fullPath }
    .do { |file| file.fullPath.load };

~omniSclorkProgramName = { |program|
    var text = program.asString;
    if(text.beginsWith("sc.sclork.")) {
        text.copyRange(10, text.size - 1).asSymbol
    } {
        nil
    }
};

~omniSclorkPlaybackGain = { |program|
    var record = playbackPrograms[program.asString]
        ? playbackPrograms[program.asSymbol];
    var gain = if(record.isNil) {
        1.0
    } {
        record["gain"] ? record[\gain] ? 1.0
    };
    gain.asFloat
};

~omniSynthHasControl = { |name, control|
    var description = SynthDescLib.global.at(name.asSymbol);
    description.notNil and: {
        description.controls.detect { |item| item.name == control.asSymbol }.notNil
    }
};

~omniFirstSynthControl = { |name, candidates|
    candidates.detect { |candidate|
        ~omniSynthHasControl.value(name, candidate)
    }
};

~omniSclorkArgs = {
    |name, outputBus, frequency, preparedArgs|
    var args = List.new;
    var mappings = Dictionary[
        "attack" -> [\att, \attack, \atk],
        "attack_ms" -> [\att, \attack, \atk],
        "decay" -> [\dec, \decay],
        "decay_ms" -> [\dec, \decay],
        "sustain" -> [\sus, \sustain],
        "release" -> [\rel, \release],
        "release_ms" -> [\rel, \release],
        "filter_hz" -> [\cutoff],
        "filter_rq" -> [\rq],
        "resonance" -> [\rq],
        "portamento_ms" -> [\lagTime, \slideTime, \glide, \freqLag, \lagamount],
        "pulse_width" -> [\width, \pw]
    ];
    args.add(\out); args.add(outputBus);
    if(frequency.notNil and: { ~omniSynthHasControl.value(name, \freq) }) {
        args.add(\freq); args.add(frequency);
    };
    if(~omniSynthHasControl.value(name, \pan)) {
        args.add(\pan); args.add(0.0);
    };
    if(~omniSynthHasControl.value(name, \gate)) {
        args.add(\gate); args.add(1.0);
    };
    preparedArgs.pairsDo { |key, rawValue|
        var candidates = mappings[key.asString] ? [key.asSymbol];
        var target = ~omniFirstSynthControl.value(name, candidates);
        var value = rawValue;
        if(["attack_ms", "decay_ms", "release_ms", "portamento_ms"]
            .includesEqual(key.asString)) {
            value = rawValue / 1000;
        };
        if(target.notNil) {
            args.add(target); args.add(value);
        };
    };
    args.asArray
};

("LB_OMNICHORD_SCLORK_LOADED count=" ++ sourceFiles.size).postln;
)
