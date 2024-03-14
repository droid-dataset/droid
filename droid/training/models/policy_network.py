import torch
import torch.utils.data
from torch import nn
from torch.nn import functional as F


class Residual(nn.Module):
    def __init__(self, in_channels, num_hiddens, num_residual_hiddens):
        super(Residual, self).__init__()
        self._block = nn.Sequential(
            nn.ReLU(True),
            nn.Conv2d(
                in_channels=in_channels,
                out_channels=num_residual_hiddens,
                kernel_size=3,
                stride=1,
                padding=1,
                bias=False,
            ),
            nn.ReLU(True),
            nn.Conv2d(in_channels=num_residual_hiddens, out_channels=num_hiddens, kernel_size=1, stride=1, bias=False),
        )

    def forward(self, x):
        return x + self._block(x)


class ResidualStack(nn.Module):
    def __init__(self, in_channels, num_hiddens, num_residual_layers, num_residual_hiddens):
        super(ResidualStack, self).__init__()
        self._num_residual_layers = num_residual_layers
        self._layers = nn.ModuleList(
            [Residual(in_channels, num_hiddens, num_residual_hiddens) for _ in range(self._num_residual_layers)]
        )

    def forward(self, x):
        for i in range(self._num_residual_layers):
            x = self._layers[i](x)
        return F.relu(x)


class Encoder(nn.Module):
    def __init__(self, in_channels, num_hiddens, num_residual_layers, num_residual_hiddens, embedding_dim):
        super(Encoder, self).__init__()

        self._conv_1 = nn.Conv2d(
            in_channels=in_channels, out_channels=num_hiddens // 2, kernel_size=4, stride=2, padding=1
        )
        self._conv_2 = nn.Conv2d(
            in_channels=num_hiddens // 2, out_channels=num_hiddens, kernel_size=4, stride=2, padding=1
        )
        self._conv_3 = nn.Conv2d(in_channels=num_hiddens, out_channels=num_hiddens, kernel_size=3, stride=1, padding=1)
        self._residual_stack = ResidualStack(
            in_channels=num_hiddens,
            num_hiddens=num_hiddens,
            num_residual_layers=num_residual_layers,
            num_residual_hiddens=num_residual_hiddens,
        )
        self._final_conv = nn.Conv2d(in_channels=num_hiddens, out_channels=embedding_dim, kernel_size=1, stride=1)

    def forward(self, inputs):
        batch_size = inputs.shape[0]

        x = self._conv_1(inputs)
        x = F.relu(x)

        x = self._conv_2(x)
        x = F.relu(x)

        x = self._conv_3(x)

        x = self._residual_stack(x)

        x = self._final_conv(x)

        return x.view(batch_size, -1)


class ImagePolicy(nn.Module):
    def __init__(
        self,
        embedding_dim=1,
        num_encoder_hiddens=128,
        num_residual_layers=3,
        num_residual_hiddens=64,
        representation_size=100,
        num_camera_layers=4,
        num_camera_hidden=400,
        num_state_layers=4,
        num_state_hidden=400,
        num_policy_layers=4,
        num_policy_hidden=400,
    ):
        super(ImagePolicy, self).__init__()

        self.representation_size = representation_size
        self.embedding_dim = embedding_dim

        self.num_encoder_hiddens = num_encoder_hiddens
        self.num_residual_layers = num_residual_layers
        self.num_residual_hiddens = num_residual_hiddens

        self.num_camera_layers = num_camera_layers
        self.num_camera_hidden = num_camera_hidden

        self.num_state_layers = num_state_layers
        self.num_state_hidden = num_state_hidden

        self.num_policy_layers = num_policy_layers
        self.num_policy_hidden = num_policy_hidden

        self.network_initialized = False
        self.loss = nn.HuberLoss()

    def create_camera_encoder(self, input_dim):
        network = nn.ModuleList([])

        encoder = Encoder(
            input_dim[1],
            self.num_encoder_hiddens,
            self.num_residual_layers,
            self.num_residual_hiddens,
            self.embedding_dim,
        )
        network.append(encoder)

        fake_input = torch.zeros(input_dim)
        output_size = encoder(fake_input).shape[1]

        fc_layers = self.create_fully_connected(
            output_size,
            self.representation_size,
            self.num_camera_layers,
            self.num_camera_hidden,
            output_activation=nn.LeakyReLU,
        )
        network.extend(fc_layers)

        return nn.Sequential(*network)

    def create_fully_connected(self, input_dim, output_dim, num_layers, num_hiddens, output_activation):
        hidden_layers = nn.ModuleList([])
        in_dim = input_dim

        for i in range(num_layers):
            if i == (num_layers - 1):
                out_dim, curr_activation = output_dim, output_activation()
            else:
                out_dim, curr_activation = num_hiddens, nn.LeakyReLU(True)

            curr_layer = nn.Linear(in_dim, out_dim)
            nn.init.xavier_uniform_(curr_layer.weight, gain=1)
            curr_layer.bias.data.uniform_(-1e-3, 1e-3)

            hidden_layers.append(curr_layer)
            hidden_layers.append(curr_activation)

            in_dim = out_dim

        return hidden_layers

    def initialize_networks(self, timestep):
        camera_dict = timestep["observation"]["camera"]
        state = timestep["observation"]["state"]
        actions = timestep["action"]

        # Create High Dimensional Networks #
        self.camera_encoder_dict = nn.ModuleDict({})
        for obs_type in camera_dict:
            self.camera_encoder_dict[obs_type] = nn.ModuleDict({})

            for cam_type in camera_dict[obs_type]:
                self.camera_encoder_dict[obs_type][cam_type] = self.create_camera_encoder(
                    camera_dict[obs_type][cam_type][0].shape
                )

        # Create State Network #
        state_encoder_network = self.create_fully_connected(
            state.shape[1],
            self.representation_size,
            self.num_state_layers,
            self.num_state_hidden,
            output_activation=nn.LeakyReLU,
        )
        self.state_encoder_network = nn.Sequential(*state_encoder_network)

        # Create Policy Network #
        latent = self.encode_timestep(timestep)
        policy_network = self.create_fully_connected(
            latent.shape[1], actions.shape[1], self.num_policy_layers, self.num_policy_hidden, output_activation=nn.Tanh
        )
        self.policy_network = nn.Sequential(*policy_network)

        # Mark As Initialized #
        self.network_initialized = True

    def compute_loss(self, timestep):
        if not self.network_initialized:
            self.initialize_networks(timestep)

        action = self.forward(timestep)
        bc_loss = self.loss(action, timestep["action"])
        return bc_loss

    def encode_timestep(self, timestep):
        # Process Timestep #
        camera_dict = timestep["observation"]["camera"]
        state = timestep["observation"]["state"]
        state.shape[0]
        latent_list = []

        # Encode State Observations #
        if state.shape[1] > 0:
            state_latent = self.state_encoder_network(state)
            latent_list.append(state_latent)

        # Encode Camera Observations #
        sorted_obs_type_keys = sorted(camera_dict.keys())
        camera_latent = []

        for obs_type in sorted_obs_type_keys:
            sorted_cam_type_keys = sorted(camera_dict[obs_type].keys())
            obs_type_latent = []

            for cam_type in sorted_cam_type_keys:
                obs_list = camera_dict[obs_type][cam_type]
                network = self.camera_encoder_dict[obs_type][cam_type]

                # Method 1 #
                encodings = [network(data) for data in obs_list]
                curr_camera_latent = torch.cat(encodings, dim=1)

                # # # Method 2 #

                # stacked_obs = torch.cat(obs_list, dim=0)
                # stacked_latent = network(stacked_obs)
                # curr_high_dim_latent_2 = stacked_latent.reshape(batch_size, -1)

                obs_type_latent.append(curr_camera_latent)

            if len(obs_type_latent):
                obs_type_latent = torch.cat(obs_type_latent, dim=1)
                camera_latent.append(obs_type_latent)

        if len(camera_latent):
            camera_latent = torch.cat(camera_latent, dim=1)
            latent_list.append(camera_latent)

        # Return Latent #
        return torch.cat(latent_list, dim=1)

    def forward(self, timestep):
        # Encode Timestep #
        latent = self.encode_timestep(timestep)

        # Pass Through Policy #
        action = self.policy_network(latent)

        return action
