/* LB routing adapter for the pinned SCLOrkSynths definition. */
SynthDef("pulseRisset", {
    |out=0, freq=440, att=0.01, rel=11, amp=0.1, pan=0, pulseFreq=8|
    var partials = ([246.4, 247.4, 404.8, 406.5, 523.6, 748, 880,
        1206, 1320, 1654, 1791] / 440) * freq;
    var durs = [11, 10, 7, 6, 4, 3.4, 3, 2.2, 2, 1.1, 1] / 11;
    var amps = durs.linlin(1, 11, 0.2, 1);
    var env = Env.perc(att, durs * rel, amps).kr(
        doneAction: [2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    );
    var signal = Pulse.ar(partials) * env * amp / 11;
    signal = RLPF.ar(
        signal,
        freq * LFPulse.ar(pulseFreq).range(2, 4),
        SinOsc.ar(LFNoise2.kr(1).range(4, 9)).range(0.1, 0.3)
    );
    signal = Limiter.ar(Mix.ar(LPF.ar(signal, 12000)));
    Out.ar(out, Pan2.ar(signal, pan));
}).add;
