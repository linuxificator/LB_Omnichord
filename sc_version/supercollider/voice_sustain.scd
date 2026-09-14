/* Owner-scoped sustain state. Musical release remains inside the SC engine. */
(
~omniSustainOwners = Dictionary.new;
~omniSustainPending = Dictionary.new;

~omniFinalizeRelease = { |handle, releaseVelocity=0|
    var record = ~omniVoices[handle.asString];
    if(record.notNil and: { ~omniFinalRelease.notNil }) {
        record[\finalized] = true;
        ~omniFinalRelease.value(record, releaseVelocity.asFloat.clip(0, 1));
    };
    ~omniReleaseHandle.value(handle);
};

~omniRequestRelease = { |handle, releaseVelocity=0|
    var record = ~omniVoices[handle.asString];
    if(record.notNil and: { record[\physicalReleased] != true }) {
        record[\physicalReleased] = true;
        if(~omniPhysicalRelease.notNil) {
            ~omniPhysicalRelease.value(
                record, releaseVelocity.asFloat.clip(0, 1)
            );
        };
    };
    if(record.notNil and: {
        ~omniSustainOwners[record[\owner].asString] == true
    }) {
        ~omniSustainPending[handle.asString] = releaseVelocity.asFloat.clip(0, 1);
    } {
        ~omniFinalizeRelease.value(handle, releaseVelocity);
    };
};

~omniSetOwnerSustain = { |owner, enabled|
    var ownerName = owner.asString;
    if(enabled) {
        ~omniSustainOwners[ownerName] = true;
    } {
        var handles = ~omniSustainPending.keys.select { |handle|
            var record = ~omniVoices[handle];
            record.notNil and: { record[\owner] == ownerName }
        }.asArray;
        ~omniSustainOwners.removeAt(ownerName);
        handles.do { |handle|
            ~omniFinalizeRelease.value(
                handle, ~omniSustainPending[handle] ? 0
            );
        };
    };
};
)
