/* Compile every pinned source without booting an audio server. */
(
var root = thisProcess.nowExecutingPath.dirname.dirname
    +/+ "vendor/SCLOrkSynths/SynthDefs";
var adapterRoot = thisProcess.nowExecutingPath.dirname.dirname +/+ "adapters";
var files = PathName(root).files;
var failures = List.new;
var successes = List.new;

PathName(root).folders.do { |folder| files = files ++ folder.files };
files = files ++ PathName(adapterRoot).files;
files = files.select { |file| file.extension == "scd" }.sort { |a, b|
    a.fullPath < b.fullPath
};

files.do { |file|
    try {
        file.fullPath.load;
        successes.add(file.fullPath);
    } { |error|
        failures.add([file.fullPath, error.asString]);
        ("SCLORK_COMPILE_FAILED " ++ file.fullPath ++ " " ++ error.asString).postln;
    };
};

("SCLORK_COMPILE_SUMMARY total=" ++ files.size
    ++ " success=" ++ successes.size
    ++ " failed=" ++ failures.size).postln;
if(failures.isEmpty) { 0.exit } { 1.exit };
)
