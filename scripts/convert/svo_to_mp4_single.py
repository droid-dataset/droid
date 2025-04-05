import tyro
from pathlib import Path
from dataclasses import dataclass
from typing import Union

from droid.postprocessing.util.svo2mp4 import export_mp4

@dataclass
class Args:
    input_path: str
    output_path: Union[str, None] = None
    overwrite: bool = False
    view: str = "left"

if __name__ == "__main__":
    args = tyro.cli(Args)
    input_path = Path(args.input_path)
    output_path = Path(args.output_path) if args.output_path else input_path.parent 

    if not input_path.exists():
        raise FileNotFoundError("Input file " + str(input_path) + " does not exist.")
    # if output_path.exists() and not args.overwrite:
    #     raise FileNotFoundError("Output path " + str(output_path) + " already exist.")

    export_mp4(input_path, output_path, stereo_view=args.view, show_progress=True)

