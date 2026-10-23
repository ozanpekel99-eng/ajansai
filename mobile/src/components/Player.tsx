import { useVideoPlayer, VideoView } from "expo-video";

export default function Player({ url, vertical = true }: { url: string; vertical?: boolean }) {
  const player = useVideoPlayer(url, (p) => {
    p.loop = true;
    p.play();
  });
  return <VideoView player={player} style={{ width: "100%", aspectRatio: vertical ? 9 / 16 : 16 / 9, borderRadius: 14, backgroundColor: "#000" }} contentFit="contain" nativeControls />;
}

