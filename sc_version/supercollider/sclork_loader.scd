/* Load the immutable upstream inventory and LB's minimal routing adapters. */
(
var directory = thisProcess.nowExecutingPath.dirname;
var sourceRoot = directory +/+ "vendor/SCLOrkSynths/SynthDefs";
var adapterRoot = directory +/+ "adapters";
var sourceFiles = List.new;

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

~omniSynthHasControl = { |name, control|
    var description = SynthDescLib.global.at(name.asSymbol);
    description.notNil and: {
        description.controls.detect { |item| item.name == control.asSymbol }.notNil
    }
};

~omniSclorkArgs = {
    |name, outputBus, frequency, preparedArgs|
    var args = List.new;
    var mappings = IdentityDictionary[
        "attack" -> \att,
        "attack_ms" -> \att,
        "decay" -> \dec,
        "decay_ms" -> \dec,
        "sustain" -> \sus,
        "release" -> \rel,
        "release_ms" -> \rel,
        "filter_hz" -> \cutoff,
        "resonance" -> \rq,
        "portamento_ms" -> \lagTime
    ];
    args.add(\out); args.add(outputBus);
    if(~omniSynthHasControl.value(name, \freq)) {
        args.add(\freq); args.add(frequency);
    };
    if(~omniSynthHasControl.value(name, \amp)) {
        args.add(\amp); args.add(1.0);
    };
    if(~omniSynthHasControl.value(name, \pan)) {
        args.add(\pan); args.add(0.0);
    };
    if(~omniSynthHasControl.value(name, \gate)) {
        args.add(\gate); args.add(1.0);
    };
    preparedArgs.pairsDo { |key, rawValue|
        var target = mappings[key.asString] ? key.asSymbol;
        var value = rawValue;
        if(["attack_ms", "decay_ms", "release_ms", "portamento_ms"]
            .includesEqual(key.asString)) {
            value = rawValue / 1000;
        };
        if(~omniSynthHasControl.value(name, target)) {
            args.add(target); args.add(value);
        };
    };
    args.asArray
};

("LB_OMNICHORD_SCLORK_LOADED count=" ++ sourceFiles.size).postln;
)
