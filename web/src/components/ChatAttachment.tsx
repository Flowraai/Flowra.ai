import { useEffect, useState } from "react";
import { attachmentObjectUrl } from "../api/client";
import type { MessageAttachment } from "../api/types";

function kind(a: MessageAttachment): "image" | "audio" | "file" {
  const ct = a.content_type ?? a.type ?? "";
  if (ct.startsWith("image/")) return "image";
  if (ct.startsWith("audio/")) return "audio";
  return "file";
}

export function ChatAttachment({ attachment }: { attachment: MessageAttachment }) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState(false);
  const id = attachment.id;
  const k = kind(attachment);

  useEffect(() => {
    if (!id) return;
    let active = true;
    let objectUrl: string | null = null;
    attachmentObjectUrl(id)
      .then((u) => {
        objectUrl = u;
        if (active) setUrl(u);
        else URL.revokeObjectURL(u);
      })
      .catch(() => active && setError(true));
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [id]);

  if (error) return <span className="att-err">anexo indisponível</span>;
  if (!url) return <span className="att-loading">carregando anexo…</span>;

  if (k === "image") {
    return (
      <a href={url} target="_blank" rel="noreferrer" className="att-image">
        <img src={url} alt={attachment.filename ?? "imagem"} />
      </a>
    );
  }
  if (k === "audio") {
    return <audio controls src={url} className="att-audio" />;
  }
  return (
    <a href={url} download={attachment.filename ?? "arquivo"} className="att-file">
      📎 {attachment.filename ?? "arquivo"}
    </a>
  );
}
