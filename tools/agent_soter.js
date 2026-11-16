import Java from 'frida-java-bridge';

function out(o) {
    send(o);
}

Java.perform(function () {
    const cls = Java.use('com.tencent.soter.soterserver.SoterService');
    const names = ['y', 'P', 'L', 'M', 'N', 'O', 'J', 'K', 'Q', 'R', 'S'];

    names.forEach(function (name) {
        let overloads;
        try {
            overloads = cls[name].overloads;
        } catch (e) {
            out({ ev: 'missing', name: name });
            return;
        }
        overloads.forEach(function (ov) {
            const sig = name + '(' + ov.argumentTypes.map(function (t) { return t.className; }).join(',') + ')';
            ov.implementation = function () {
                const args = Array.prototype.slice.call(arguments).map(function (a) { return String(a); });
                out({ ev: 'call', sig: sig, args: args });
                try {
                    const r = ov.call(this, ...arguments);
                    out({ ev: 'ret', sig: sig, ret: String(r) });
                    return r;
                } catch (e) {
                    out({ ev: 'throw', sig: sig, err: String(e) });
                    throw e;
                }
            };
        });
    });

    out({ ev: 'ready' });
});
