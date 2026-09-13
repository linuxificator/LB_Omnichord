/* LB routing adapter for the pinned SCLOrkSynths definition. */
SynthDef("waveguideFlute", {
    |out=0, scl=0.2, freq=440, ipress=0.9, ibreath=0.09,
     ifeedbk1=0.4, ifeedbk2=0.4, dur=1, gate=1, amp=2|
    var sr = SampleRate.ir;
    var cr = ControlRate.ir;
    var block = cr.reciprocal;
    var pressure = EnvGen.kr(
        Env.new(
            [0.0, 1.1 * ipress, ipress, ipress, 0.0],
            [0.06, 0.2, dur - 0.46, 0.2],
            \linear
        )
    );
    var amplitude = EnvGen.kr(
        Env.new([0.0, amp, amp, 0.0], [0.1, dur - 0.02, 0.1], \linear),
        doneAction: 2
    );
    var vibratoEnvelope = EnvGen.kr(
        Env.new([0.0, 0.0, 1, 1, 0.0], [0.5, 0.5, dur - 1.5, 0.5], \linear)
    );
    var flow = LFClipNoise.ar(sr, pressure);
    var vibrato = SinOsc.ar(5, 0, 0.1 * vibratoEnvelope);
    var excitation = (ibreath * flow) + pressure + vibrato;
    var delay = freq.reciprocal - (excitation / 20000)
        - (9 / sr) + (freq / 12000000) - block;
    var feedback = LocalIn.ar(1);
    var bore = DelayC.ar(
        excitation + (feedback * ifeedbk1),
        freq.reciprocal - (block * 0.5),
        (delay * 0.5) - (excitation / freq / cr) + 0.001
    );
    var shaped = bore - bore.cubed + (feedback * ifeedbk2);
    var signal = LPF.ar(shaped, 2000);
    LocalOut.ar(DelayC.ar(signal, freq.reciprocal - block, delay));
    OffsetOut.ar(out, (signal * amplitude) ! 2);
}).add;
