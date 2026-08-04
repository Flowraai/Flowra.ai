// Seleção de foto/arquivo e gravação de áudio, com upload como anexo.

import * as ImagePicker from "expo-image-picker";
import * as DocumentPicker from "expo-document-picker";
import { Audio } from "expo-av";
import { patientApi } from "./api/endpoints";
import type { AttachmentRef } from "./api/types";

export async function pickAndUploadPhoto(): Promise<AttachmentRef | null> {
  const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
  if (!perm.granted) return null;
  const res = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ImagePicker.MediaTypeOptions.Images,
    quality: 0.7,
  });
  if (res.canceled || res.assets.length === 0) return null;
  const a = res.assets[0];
  return patientApi.uploadAttachment({
    uri: a.uri,
    name: a.fileName ?? "foto.jpg",
    type: a.mimeType ?? "image/jpeg",
  });
}

export async function pickAndUploadFile(): Promise<AttachmentRef | null> {
  const res = await DocumentPicker.getDocumentAsync({ copyToCacheDirectory: true });
  if (res.canceled || res.assets.length === 0) return null;
  const a = res.assets[0];
  return patientApi.uploadAttachment({
    uri: a.uri,
    name: a.name,
    type: a.mimeType ?? "application/octet-stream",
  });
}

/** Controle simples de gravação de áudio. */
export class AudioRecorder {
  private recording: Audio.Recording | null = null;

  async start(): Promise<boolean> {
    const perm = await Audio.requestPermissionsAsync();
    if (!perm.granted) return false;
    await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });
    const rec = new Audio.Recording();
    await rec.prepareToRecordAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
    await rec.startAsync();
    this.recording = rec;
    return true;
  }

  async stopAndUpload(): Promise<AttachmentRef | null> {
    const rec = this.recording;
    this.recording = null;
    if (!rec) return null;
    await rec.stopAndUnloadAsync();
    const uri = rec.getURI();
    if (!uri) return null;
    return patientApi.uploadAttachment({ uri, name: "audio.m4a", type: "audio/mp4" });
  }
}
