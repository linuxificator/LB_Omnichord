/* Owner-scoped sustain state. Musical release remains inside the SC engine. */
(
~omniSustainOwners = Dictionary.new;
~omniSustainPending = Dictionary.new;

~omniRequestRelease = { |handle|
    var record = ~omniVoices[handle.asString];
    if(record.notNil and: {
        ~omniSustainOwners[record[\owner].asString] == true
    }) {
        ~omniSustainPending[handle.asString] = true;
    } {
        ~omniReleaseHandle.value(handle);
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
        handles.do(~omniReleaseHandle);
    };
};
)
