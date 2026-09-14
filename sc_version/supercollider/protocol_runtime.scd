/* Bounded replay protection shared by every typed live-control endpoint. */

~omniMessageIds = IdentitySet.new;
~omniMessageIdOrder = List.new;
~omniMaxMessageIds = 4096;

~omniAcceptMessageId = { |messageId|
    var value = messageId.asInteger;
    var accepted = ~omniMessageIds.includes(value).not;
    if(accepted) {
        ~omniMessageIds.add(value);
        ~omniMessageIdOrder.add(value);
        while { ~omniMessageIdOrder.size > ~omniMaxMessageIds } {
            ~omniMessageIds.remove(~omniMessageIdOrder.removeAt(0));
        };
    };
    accepted
};

~omniCommandValid = { |message|
    ~omniReady
    and: { ~omniSessionValid.value(message) }
    and: { ~omniAcceptMessageId.value(message[2]) }
};
