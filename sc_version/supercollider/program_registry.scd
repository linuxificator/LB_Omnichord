/* Owner-scoped immutable program revisions and parameter lookup. */
(
~omniPrograms = Dictionary.new;

~omniProgramKey = { |owner, program, revision|
    owner.asString ++ "/" ++ program.asString ++ "@"
        ++ revision.asInteger.asString
};

~omniPreparedArgs = { |owner, program, revision|
    var record = ~omniPrograms[
        ~omniProgramKey.value(owner, program, revision)
    ];
    var args = List.new;
    if(record.notNil) {
        record[\values].keysValuesDo { |name, value|
            args.add(name.asSymbol);
            args.add(value);
        };
    };
    args.asArray
};

~omniGenericArgs = { |owner, program, revision|
    var args = List.new;
    ~omniPreparedArgs.value(owner, program, revision).pairsDo { |name, value|
        if([\gain, \attack, \release, \brightness].includes(name)) {
            args.add(name); args.add(value);
        };
    };
    args.asArray
};

// Program/revision is session-unique.  A chord program intentionally has two
// owner records (manual and automatic), so release removes that exact revision
// for every owner without affecting any later revision.
~omniReleaseProgram = { |program, revision|
    var removed = 0;
    ~omniPrograms.keys.asArray.do { |key|
        var record = ~omniPrograms[key];
        if(record.notNil and: {
            record[\program] == program.asString and: {
                record[\revision] == revision.asInteger
            }
        }) {
            ~omniPrograms.removeAt(key);
            removed = removed + 1;
        };
    };
    removed
};
)
