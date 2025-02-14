import pybullet as p
import pybullet_data
import numpy as np
import math


ll = [-7] * 7
# upper limits for null space (todo: set them to proper range)
ul = [7] * 7
# joint ranges for null space (todo: set them to proper range)
jr = [7] * 7
# restposes for null space
# jointPositions = [0, -1 * math.pi / 4, 0, -3 * math.pi / 4, 0, math.pi / 2, math.pi / 4, 0.04, 0.04]
jointPositions = [0.00, 0.41, 0.00, -1.85, -0.00, 2.26, 0.79, 0.04, 0.04]
rp = jointPositions


class RCareWorldController:
    """
    RCareWorldController is a class to generate robot arm joint states. In simulation environment, we mostly
    want to specify the 6DoF of a joint, then the robot arm will automatically move to that state. Thus, here
    we use pybullet.calculateInverseKinematics() to generate joint positions based on a given robot arm, a
    given end-effector joint and a target Cartesian position. The generated joint states will be passed to
    Unity by rfuniverse channels. Besides, this class will also provide functions to align coordinate in Unity
    and in pybullet.

    TODO: Currently, this class has many hard codes for Franka, need further refinement.
    """

    def __init__(
        self,
        robot_name,
        robot_urdf=None,
        base_pos=np.array([0, 0, 0]),
        base_orn=[-0.707107, 0.0, 0.0, 0.707107],
        end_effector_id=None,
        render=False,
    ):
        if render:
            p.connect(p.GUI)  # For debug mode
        else:
            p.connect(p.DIRECT)

        p.configureDebugVisualizer(p.COV_ENABLE_Y_AXIS_UP, 1)
        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        p.setGravity(0, -9.8, 0)

        self.bullet_client = p
        self.bullet_flags = self.bullet_client.URDF_ENABLE_CACHED_GRAPHICS_SHAPES

        self.robot_name = robot_name
        self.robot_urdf = robot_urdf
        self.end_effector_id = end_effector_id
        self.num_dof = None
        self._parse_robot_params()

        self.robot = self.bullet_client.loadURDF(
            self.robot_urdf,
            base_pos,
            base_orn,
            useFixedBase=True,
            flags=self.bullet_flags,
        )

        # Magic starts
        self.revolute_joint_ids = []
        self.prismatic_joint_ids = []
        index = 0
        for j in range(self.bullet_client.getNumJoints(self.robot)):
            self.bullet_client.changeDynamics(
                self.robot, j, linearDamping=0, angularDamping=0
            )
            info = self.bullet_client.getJointInfo(self.robot, j)

            jointName = info[1]
            jointType = info[2]
            if jointType == self.bullet_client.JOINT_PRISMATIC:
                self.bullet_client.resetJointState(self.robot, j, jointPositions[index])
                self.prismatic_joint_ids.append(j)
                index = index + 1
            if jointType == self.bullet_client.JOINT_REVOLUTE:
                self.bullet_client.resetJointState(self.robot, j, jointPositions[index])
                self.revolute_joint_ids.append(j)
                index = index + 1

        # print('pybullet', self.get_link_state(self.end_effector_id))

    def _parse_robot_params(self):
        if self.robot_name == "franka":
            self.robot_urdf = "franka_panda/panda.urdf"
            self.end_effector_id = 11
            self.num_dof = 7
            return
        elif self.robot_name == "tobor":
            self.end_effector_id = 6
            self.num_dof = 7
            return
        elif self.robot_name == "ur5":
            self.num_dof = 6

        # elif self.robot_name == 'another_known_robot':
        #     self.robot_urdf = 'known_urdf_path'
        #     return

        elif self.robot_urdf is None:
            print("Error: an unknown robot name without an input urdf.")
            exit(-1)

    def get_bullet_pos_from_unity(self, unity_pos: list) -> list:
        return [-1 * unity_pos[0], unity_pos[1], unity_pos[2]]

    def get_unity_pos_from_bullet(self, bullet_pos: list) -> list:
        return [-1 * bullet_pos[0], bullet_pos[1], bullet_pos[2]]

    def get_unity_joint_pos_from_pybullet(self, pybullet_joint_pos: tuple) -> list:
        pybullet_joint_pos = list(pybullet_joint_pos)[: self.num_dof]
        for i, (joint_pos) in enumerate(pybullet_joint_pos):
            pybullet_joint_pos[i] = -180 * joint_pos / math.pi

        return pybullet_joint_pos

    def calculate_ik(self, unity_eef_pos, eef_orn=None) -> list:
        if eef_orn is None:
            eef_orn = self.bullet_client.getQuaternionFromEuler(
                [math.pi / 2.0, 0.0, 0.0]
            )

        eef_pos = self.get_bullet_pos_from_unity(unity_eef_pos)

        joint_positions = self.bullet_client.calculateInverseKinematics(
            self.robot,
            self.end_effector_id,
            eef_pos,
            eef_orn,
            ll,
            ul,
            jr,
            rp,
            maxNumIterations=20,
        )

        for i, (idx) in enumerate(self.revolute_joint_ids):
            self.bullet_client.resetJointState(self.robot, idx, joint_positions[i])

        return self.get_unity_joint_pos_from_pybullet(joint_positions)

    def calculate_ik_recursive(self, unity_eef_pos, eef_orn=None) -> list:
        if eef_orn is None:
            eef_orn = self.bullet_client.getQuaternionFromEuler(
                [math.pi / 2.0, 0.0, 0.0]
            )

        eef_pos = self.get_bullet_pos_from_unity(unity_eef_pos)
        for i in range(20):
            joint_positions = self.bullet_client.calculateInverseKinematics(
                self.robot,
                self.end_effector_id,
                eef_pos,
                eef_orn,
                ll,
                ul,
                jr,
                rp,
                maxNumIterations=20,
            )

            for i, (idx) in enumerate(self.revolute_joint_ids):
                self.bullet_client.resetJointState(self.robot, idx, joint_positions[i])

        return self.get_unity_joint_pos_from_pybullet(joint_positions)

    def get_link_state(self, link_idx):
        link_state = self.bullet_client.getLinkState(self.robot, link_idx)

        return self.get_unity_pos_from_bullet(link_state[0])

    def reset(self):
        for i, (idx) in enumerate(self.revolute_joint_ids):
            self.bullet_client.resetJointState(self.robot, idx, jointPositions[i])
