/* Preserve upstream acidOto3091 while bounding its filter over the UI register. */
SynthDef("acidOto3091", {
    |out=0, gate=1, freq=440, amp=0.1, pan=0,
     att=0.001, dec=0.5, sus=0.1, rel=0.5, curve=(-4),
     lagTime=0.12, filterRange=6, width=0.51, rq=0.3|
    var pitched = Lag.kr(freq, lagTime);
    var ampEnv = Env.adsr(att, dec, sus, rel, amp, [0, curve, curve, curve])
        .kr(gate: gate);
    var filterEnv = Env.adsr(
        att, dec * 2, sus / 2, rel * 2,
        2.pow(filterRange), [-1 * curve, curve, curve, curve], 1
    ).kr(gate: gate, doneAction: Done.freeSelf);
    var signal = LFPulse.ar(pitched, width: width).range(-1, 1);
    var cutoff = (pitched * filterEnv).clip(20, SampleRate.ir * 0.45);

    signal = RLPF.ar(signal, cutoff, rq) * ampEnv;
    Out.ar(out, Pan2.ar(signal, pan));
}).add;
