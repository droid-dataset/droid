import cv2
from torchvision import transforms as T


class ImageTransformer:
    def __init__(
        self, remove_alpha=False, bgr_to_rgb=False, augment=False, to_tensor=False, image_path="observation/camera/image"
    ):
        self.image_path = image_path.split("/")
        self.apply_transforms = any([remove_alpha, bgr_to_rgb, augment, to_tensor])

        # Build Composed Transform #
        transforms = []

        if remove_alpha:
            new_transform = T.Lambda(lambda data: data[:, :, :3])
            transforms.append(new_transform)

        if bgr_to_rgb:

            def helper(data):
                if data.shape[-1] == 4:
                    return cv2.cvtColor(data, cv2.COLOR_BGRA2RGBA)
                return cv2.cvtColor(data, cv2.COLOR_BGR2RGB)

            new_transform = T.Lambda(lambda data: helper(data))
            transforms.append(new_transform)

        if augment:
            transforms.append(T.ToPILImage())
            transforms.append(T.AugMix())

        if to_tensor:
            transforms.append(T.ToTensor())

        self.composed_transforms = T.Compose(transforms)

    def forward(self, timestep):
        # Skip If Unnecesary #
        if not self.apply_transforms:
            return timestep

        # Isolate Image Data #
        obs = timestep
        for key in self.image_path:
            obs = obs[key]

        # Apply Transforms #
        for cam_type in obs:
            for i in range(len(obs[cam_type])):
                data = self.composed_transforms(obs[cam_type][i])
                obs[cam_type][i] = data
