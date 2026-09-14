/* Preserve upstream combs while bounding both filters over the UI register. */
SynthDef("combs", {
    |out=0, pan=0, amp=0.1, freq=440, gate=1,
     att=0.01, dec=0.1, sus=0.7, rel=0.5,
     rate=6, depth=0.2, regen=(-3), sweep=16, rq=0.5, harmonic=1.5|
    var maximum = ((1 + depth) / freq);
    var minimum = (1 / (freq * (1 + depth)));
    var vibrato = LFNoise1.ar(rate).range(minimum, maximum);
    var envelope = Env.adsr(att, dec, sus, rel).kr(
        gate: gate, doneAction: Done.freeSelf
    );
    var filterEnvelope = ((Env.perc(att, rel).kr * sweep) + 1) * freq;
    var signal = BrownNoise.ar(1);

    signal = CombL.ar(signal, maximum, vibrato, regen);
    signal = CombN.ar(signal, harmonic / freq, harmonic / freq, regen, envelope);
    signal = RHPF.ar(
        signal, (freq * 4).clip(20, SampleRate.ir * 0.45), rq
    );
    signal = RLPF.ar(
        signal, filterEnvelope.clip(20, SampleRate.ir * 0.45), rq, amp
    );
    signal = Limiter.ar(signal, amp);
    Out.ar(out, Pan2.ar(signal, pan));
}).add;
