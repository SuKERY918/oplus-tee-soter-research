// Fake cryptoeng cmd 61 (RKP CSR) so the engineering page shows "RKP default success".
// The page only reads the first 8 bytes of the reply; SecurityInterface.genRkpInfo()
// treats offset 4 as the status and then caches rkpdefault_import in Settings.Global.
//
// usage:
//   frida -U -p <pid of vendor.oplus.hardware.cryptoeng@1.0-service> -l fake61.js -q
//
// note: this is cosmetic only. It does not provision RKP and does not affect SOTER.

const MODULE = 'vendor.oplus.hardware.cryptoeng@1.0-service';
const DISPATCHER_OFFSET = 0x1415c;
const CMD_RKP = 0x3d;

const mod = Process.findModuleByName(MODULE);
if (mod === null) {
    throw new Error(MODULE + ' not loaded');
}

const dispatcher = mod.base.add(DISPATCHER_OFFSET);
const orig = new NativeFunction(dispatcher, 'int', ['pointer', 'pointer', 'uint', 'pointer', 'pointer']);

Interceptor.replace(dispatcher, new NativeCallback(function (dev, inPtr, inLen, outPtr, outLenPtr) {
    if (!inPtr.isNull() && inLen >= 4 && inPtr.readU32() === CMD_RKP) {
        outPtr.writeByteArray([0, 0, 0, 0, 0, 0, 0, 0]);
        if (!outLenPtr.isNull()) {
            outLenPtr.writeU32(8);
        }
        send({ ev: 'fake61', pid: Process.id });
        return 0;
    }
    return orig(dev, inPtr, inLen, outPtr, outLenPtr);
}, 'int', ['pointer', 'pointer', 'uint', 'pointer', 'pointer']));

send({ ev: 'ready', module: MODULE, base: mod.base.toString(), dispatcher: dispatcher.toString() });
