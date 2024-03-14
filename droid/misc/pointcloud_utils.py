import cv2
import numpy as np
import open3d as o3d
from scipy.spatial.transform import Rotation as R

# VOXEL_SIZE = 0.02
VOXEL_SIZE = 0.001
MAX_DISTANCE_COARSE = VOXEL_SIZE * 15
MAX_DISTANCE_FINE = VOXEL_SIZE * 1.5


def numpy_to_o3d(numpy_pcd):
    xyz = numpy_pcd[:, :, :3].reshape(-1, 3)

    rgba_size = (*numpy_pcd.shape[:2], 4)
    rgba_float = np.ascontiguousarray(numpy_pcd[:, :, 3])
    rgba = rgba_float.view(np.uint8).reshape(rgba_size)
    rgb = rgba[:, :, :3].reshape(-1, 3)

    o3d_pcd = o3d.geometry.PointCloud()
    o3d_pcd.points = o3d.utility.Vector3dVector(xyz)
    o3d_pcd.colors = o3d.utility.Vector3dVector(rgb)
    o3d_pcd = o3d_pcd.voxel_down_sample(voxel_size=VOXEL_SIZE)
    return o3d_pcd


def o3d_to_numpy(o3d_pcd):
    points = np.asarray(o3d_pcd.points)
    colors = np.asarray(o3d_pcd.colors)
    numpy_pcd = np.concatenate([points, colors], axis=1)
    return numpy_pcd


def rgbd_to_pcd(color, depth, camera_matrix):
    color = cv2.cvtColor(color, cv2.COLOR_BGRA2RGB)
    o3d_color = o3d.geometry.Image(color)
    o3d_depth = o3d.geometry.Image(depth)
    rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(o3d_color, o3d_depth, convert_rgb_to_intensity=False)
    intrinsics = o3d.camera.PinholeCameraIntrinsic(
        width=color.shape[1],
        height=color.shape[0],
        fx=camera_matrix[0, 0],
        cx=camera_matrix[0, 2],
        fy=camera_matrix[1, 1],
        cy=camera_matrix[1, 2],
    )

    o3d_pcd = o3d.geometry.PointCloud.create_from_rgbd_image(rgbd, intrinsics)
    # o3d_pcd = o3d.geometry.PointCloud.create_from_depth_image(o3d_depth, intrinsics)
    o3d_pcd = o3d_pcd.voxel_down_sample(voxel_size=VOXEL_SIZE)
    o3d_pcd.estimate_normals()

    return o3d_pcd


def visualize_pointcloud(pcd):
    if type(pcd) == np.ndarray:
        pcd = numpy_to_o3d(pcd)
    o3d.visualization.draw_geometries([pcd])


def transform_pointcloud(pcd, cam2base):
    rotation = R.from_euler("xyz", cam2base[3:]).as_matrix()
    translation = cam2base[:3]

    pcd.rotate(rotation)
    pcd.translate(translation)


def pairwise_registration(source, target):
    print("Apply point-to-plane ICP")
    icp_coarse = o3d.pipelines.registration.registration_icp(
        source,
        target,
        MAX_DISTANCE_COARSE,
        np.identity(4),
        o3d.pipelines.registration.TransformationEstimationPointToPlane(),
    )
    icp_fine = o3d.pipelines.registration.registration_icp(
        source,
        target,
        MAX_DISTANCE_FINE,
        icp_coarse.transformation,
        o3d.pipelines.registration.TransformationEstimationPointToPlane(),
    )
    transformation_icp = icp_fine.transformation
    information_icp = o3d.pipelines.registration.get_information_matrix_from_point_clouds(
        source, target, MAX_DISTANCE_FINE, icp_fine.transformation
    )
    return transformation_icp, information_icp


def full_registration(pcds):
    pose_graph = o3d.pipelines.registration.PoseGraph()
    odometry = np.identity(4)
    pose_graph.nodes.append(o3d.pipelines.registration.PoseGraphNode(odometry))
    n_pcds = len(pcds)
    for source_id in range(n_pcds):
        for target_id in range(source_id + 1, n_pcds):
            transformation_icp, information_icp = pairwise_registration(pcds[source_id], pcds[target_id])
            if target_id == source_id + 1:  # odometry case
                odometry = np.dot(transformation_icp, odometry)
                pose_graph.nodes.append(o3d.pipelines.registration.PoseGraphNode(np.linalg.inv(odometry)))
                pose_graph.edges.append(
                    o3d.pipelines.registration.PoseGraphEdge(
                        source_id, target_id, transformation_icp, information_icp, uncertain=False
                    )
                )
            else:  # loop closure case
                pose_graph.edges.append(
                    o3d.pipelines.registration.PoseGraphEdge(
                        source_id, target_id, transformation_icp, information_icp, uncertain=True
                    )
                )
    return pose_graph


def combine_pointclouds(o3d_pcd_dict, cam2base_dict=None, reference_key=None):
    # Create O3D Pointcloud Objects + Align Them With Robot Base #
    # o3d_pcd_dict = {pcd_id: numpy_to_o3d(pcd) for pcd_id, pcd in pointcloud_dict.items()}
    if cam2base_dict is not None:
        [transform_pointcloud(o3d_pcd_dict[key], cam2base_dict[key]) for key in cam2base_dict]
    pcd_list = [o3d_pcd_dict[key] for key in o3d_pcd_dict]

    # Set Reference Frame For Merged Pointcloud #
    if reference_key:
        pcd_list.remove(o3d_pcd_dict[reference_key])
        pcd_list.insert(0, o3d_pcd_dict[reference_key])

    pose_graph = full_registration(pcd_list)
    print("Optimizing...")
    option = o3d.pipelines.registration.GlobalOptimizationOption(
        max_correspondence_distance=MAX_DISTANCE_FINE, edge_prune_threshold=0.25, reference_node=0
    )

    o3d.pipelines.registration.global_optimization(
        pose_graph,
        o3d.pipelines.registration.GlobalOptimizationLevenbergMarquardt(),
        o3d.pipelines.registration.GlobalOptimizationConvergenceCriteria(),
        option,
    )

    print("Downsizing...")
    pcd_combined = o3d.geometry.PointCloud()
    for point_id in range(len(pcd_list)):
        pcd_list[point_id].transform(pose_graph.nodes[point_id].pose)
        pcd_combined += pcd_list[point_id]
    pcd_combined_down = pcd_combined.voxel_down_sample(voxel_size=VOXEL_SIZE)

    print("Visualizing...")
    visualize_pointcloud(pcd_combined_down)

    # numpy_pcd = o3d_to_numpy(pcd_combined_down)

    return pcd_combined_down
