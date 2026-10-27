import argparse

from app.config import load_config
from app.pipeline import ViolationPipeline


def main():
    ap = argparse.ArgumentParser(description="Traffic violation detection")
    ap.add_argument("--source", required=True, help="video path or webcam index")
    ap.add_argument("--config", default=None)
    ap.add_argument("--show", action="store_true", help="live preview (press q to quit)")
    ap.add_argument("--save-video", default=None, help="write annotated video to this path")
    args = ap.parse_args()

    pipeline = ViolationPipeline(load_config(args.config))
    records = pipeline.run(args.source, show=args.show, save_video=args.save_video)

    print(f"\n{len(records)} violation(s) detected")
    for r in records:
        print(f"  [{r['type']}] track #{r['track_id']} frame {r['frame_idx']} {r['details']}")


if __name__ == "__main__":
    main()