/** Pembungkus tipis OneSignal Web SDK v16. Tanpa NEXT_PUBLIC_ONESIGNAL_APP_ID semuanya nonaktif. */

export const ONESIGNAL_APP_ID = process.env.NEXT_PUBLIC_ONESIGNAL_APP_ID ?? "";
export const pushConfigured = ONESIGNAL_APP_ID.length > 0;

interface OneSignalApi {
  init: (opts: Record<string, unknown>) => Promise<void>;
  login: (externalId: string) => Promise<void>;
  logout: () => Promise<void>;
  Notifications: {
    permission: boolean;
    requestPermission: () => Promise<void>;
    addEventListener: (ev: "permissionChange", cb: () => void) => void;
  };
  User: { PushSubscription: { optedIn?: boolean; optIn: () => Promise<void>; optOut: () => Promise<void> } };
}

declare global {
  interface Window {
    OneSignalDeferred?: Array<(os: OneSignalApi) => void | Promise<void>>;
  }
}

let loader: Promise<OneSignalApi> | null = null;

/** Muat SDK sekali dan inisialisasi. Mengembalikan null bila tidak dikonfigurasi atau perangkat tidak mendukung. */
export function loadOneSignal(): Promise<OneSignalApi | null> {
  if (!pushConfigured || typeof window === "undefined") return Promise.resolve(null);
  if (!("serviceWorker" in navigator) || !("Notification" in window)) return Promise.resolve(null);
  if (!loader) {
    loader = new Promise<OneSignalApi>((resolve, reject) => {
      window.OneSignalDeferred = window.OneSignalDeferred || [];
      window.OneSignalDeferred.push(async (os) => {
        try {
          await os.init({
            appId: ONESIGNAL_APP_ID,
            serviceWorkerPath: "sw.js",
            serviceWorkerParam: { scope: "/" },
            allowLocalhostAsSecureOrigin: true,
            notifyButton: { enable: false },
          });
          resolve(os);
        } catch (e) {
          reject(e);
        }
      });
      const s = document.createElement("script");
      s.src = "https://cdn.onesignal.com/sdks/web/v16/OneSignalSDK.page.js";
      s.defer = true;
      s.onerror = () => reject(new Error("SDK OneSignal gagal dimuat"));
      document.head.appendChild(s);
    }).catch((e) => {
      loader = null;
      throw e;
    });
  }
  return loader.catch(() => null);
}

export type PushState = "unconfigured" | "unsupported" | "denied" | "off" | "on";

export async function getPushState(): Promise<PushState> {
  if (!pushConfigured) return "unconfigured";
  const os = await loadOneSignal();
  if (!os) return "unsupported";
  if (typeof Notification !== "undefined" && Notification.permission === "denied") return "denied";
  return os.Notifications.permission && os.User.PushSubscription.optedIn ? "on" : "off";
}

export async function enablePush(): Promise<PushState> {
  const os = await loadOneSignal();
  if (!os) return "unsupported";
  await os.Notifications.requestPermission();
  if (Notification.permission === "granted") await os.User.PushSubscription.optIn();
  return getPushState();
}

export async function disablePush(): Promise<PushState> {
  const os = await loadOneSignal();
  if (os) await os.User.PushSubscription.optOut();
  return getPushState();
}

export async function pushLogin(userId: string): Promise<void> {
  const os = await loadOneSignal();
  if (os) await os.login(userId);
}

export async function pushLogout(): Promise<void> {
  const os = await loadOneSignal();
  if (os) await os.logout();
}

/** iOS hanya mengizinkan push untuk PWA yang sudah dipasang ke layar utama. */
export function needsIosInstall(): boolean {
  if (typeof navigator === "undefined") return false;
  const ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
  const standalone = window.matchMedia("(display-mode: standalone)").matches || (navigator as unknown as { standalone?: boolean }).standalone === true;
  return ios && !standalone;
}
