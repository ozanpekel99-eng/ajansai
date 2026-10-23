// Üretilen görsel/videoyu galeriye kaydetme ve paylaşma.
import { Directory, File, Paths } from "expo-file-system";
import { Asset, requestPermissionsAsync } from "expo-media-library";
import * as Sharing from "expo-sharing";
import { Linking, Platform } from "react-native";

async function download(url: string): Promise<File> {
  const dir = new Directory(Paths.cache, "ajansai");
  if (!dir.exists) dir.create({ intermediates: true });
  const name = url.split("?")[0].split("/").pop() || `ajansai-${Date.now()}`;
  const target = new File(dir, name);
  if (target.exists) return target;
  return File.downloadFileAsync(url, target);
}

/** Galeriye kaydeder. Başarılıysa true döner. */
export async function saveToGallery(url: string): Promise<boolean> {
  if (Platform.OS === "web") {
    await Linking.openURL(url);
    return true;
  }
  const perm = await requestPermissionsAsync(true);
  if (!perm.granted) return false;
  const file = await download(url);
  await Asset.create(file.uri);
  return true;
}

export async function shareMedia(url: string) {
  if (Platform.OS === "web" || !(await Sharing.isAvailableAsync())) {
    await Linking.openURL(url);
    return;
  }
  const file = await download(url);
  await Sharing.shareAsync(file.uri);
}
