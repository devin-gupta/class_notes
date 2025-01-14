import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray
import numpy as np
np.set_printoptions(precision=3, suppress=True)

Kp = 3
Kd = 0.1

class InverseKinematics(Node):

    def __init__(self):
        super().__init__('inverse_kinematics')
        self.joint_subscription = self.create_subscription(
            JointState,
            'joint_states',
            self.listener_callback,
            10)
        self.joint_subscription  # prevent unused variable warning

        self.command_publisher = self.create_publisher(
            Float64MultiArray,
            '/forward_command_controller/commands',
            10
        )

        self.pd_timer_period = 1.0 / 200  # 200 Hz
        self.ik_timer_period = 1.0 / 20   # 10 Hz
        self.pd_timer = self.create_timer(self.pd_timer_period, self.pd_timer_callback)
        self.ik_timer = self.create_timer(self.ik_timer_period, self.ik_timer_callback)

        self.joint_positions = None
        self.joint_velocities = None
        self.target_joint_positions = None

        self.ee_triangle_positions = np.array([
            [0.05, 0.0, -0.12],  # Touchdown
            [-0.05, 0.0, -0.12], # Liftoff
            [0.0, 0.0, -0.06]    # Mid-swing
        ])

        center_to_rf_hip = np.array([0.07500, -0.08350, 0])
        self.ee_triangle_positions = self.ee_triangle_positions + center_to_rf_hip
        self.current_target = 0
        self.t = 0

    def listener_callback(self, msg):
        joints_of_interest = ['leg_front_r_1', 'leg_front_r_2', 'leg_front_r_3']
        self.joint_positions = np.array([msg.position[msg.name.index(joint)] for joint in joints_of_interest])
        self.joint_velocities = np.array([msg.velocity[msg.name.index(joint)] for joint in joints_of_interest])

    def forward_kinematics(self, theta1, theta2, theta3):

        def rotation_x(angle):
            # rotation about the x-axis implemented for you
            return np.array([
                [1, 0, 0, 0],
                [0, np.cos(angle), -np.sin(angle), 0],
                [0, np.sin(angle), np.cos(angle), 0],
                [0, 0, 0, 1]
            ])

        def rotation_y(angle): 
            ## TODO: Implement the rotation matrix about the y-axis
            return np.array([
                [np.cos(angle), 0, np.sin(angle), 0],
                [0, 1, 0, 0],
                [-np.sin(angle), 0, np.cos(angle), 0],
                [0, 0, 0, 1]
            ])
        
        def rotation_z(angle):
            ## TODO: Implement the rotation matrix about the z-axis
            return np.array([
                [np.cos(angle), -np.sin(angle), 0, 0],
                [np.sin(angle), np.cos(angle), 0, 0],
                [0, 0, 1, 0],
                [0, 0, 0, 1]
            ])

        def translation(x, y, z):
            ## TODO: Implement the translation matrix
            return np.array([
                [1, 0, 0, x],
                [0, 1, 0, y],
                [0, 0, 1, z],
                [0, 0, 0, 1]
            ])

        # T_0_1 (base_link to leg_front_r_1)
        # T_0_1 = translation(0.07500, -0.0445, 0) @ rotation_x(1.57080) @ rotation_z(theta1)
        T_0_1 = translation(0.07500, -0.08350, 0) @ rotation_x(1.57080) @ rotation_z(theta1)

        # T_1_2 (leg_front_r_1 to leg_front_r_2)
        ## TODO: Implement the transformation matrix from leg_front_r_1 to leg_front_r_2
        # T_1_2 = translation(0, 0, 0.039) @ rotation_y(-1.57080) @ rotation_z(theta2)
        T_1_2 = rotation_y(-1.57080) @ rotation_z(theta2)

        # T_2_3 (leg_front_r_2 to leg_front_r_3)
        ## TODO: Implement the transformation matrix from leg_front_r_2 to leg_front_r_3
        T_2_3 = translation(0, -0.0494, 0.0685) @ rotation_y(1.57080) @ rotation_z(theta3)

        # T_3_ee (leg_front_r_3 to end-effector)
        T_3_ee = translation(0.06231, -0.06216, 0.018)

        # TODO: Compute the final transformation. T_0_ee is a concatenation of the previous transformation matrices
        T_0_ee = T_0_1 @ T_1_2 @ T_2_3 @ T_3_ee

        # TODO: Extract the end-effector position. The end effector position is a 3 vector (not in homogenous coordinates)
        end_effector_position = (T_0_ee @ np.array([0, 0, 0, 1]))[:3]

        return end_effector_position

    def inverse_kinematics(self, target_ee, initial_guess=[0, 0, 0]):
        def cost_function(theta):
            # Compute the cost function and the L1 norm of the error
            # return the cost and the L1 norm of the error

            target_current_difference = self.forward_kinematics(theta[0], theta[1], theta[2]) - target_ee

            cost = np.sum(target_current_difference ** 2)
            errorNorm = np.sum(np.abs(target_current_difference))

            return cost, errorNorm

        def gradient(theta, epsilon=1e-3):
            # Compute the gradient of the cost function using finite differences

            # cost_plus = cost_function(theta + epsilon)[0]
            # cost_minus = cost_function(theta - epsilon)[0]

            # grad = (cost_plus - cost_minus) / (2 * epsilon)

            grad = np.zeros_like(theta)

            for i in range(len(theta)):
                
                theta_plus = theta.copy()
                theta_plus[i] += epsilon

                theta_minus = theta.copy()
                theta_minus[i] -= epsilon

                cost_plus = cost_function(theta_plus)[0]
                cost_minus = cost_function(theta_minus)[0]

                grad[i] = (cost_plus - cost_minus) / (2 * epsilon)

            return grad

        theta = np.array(initial_guess)
        learning_rate = 10 # TODO: Set the learning rate
        max_iterations = 50 # TODO: Set the maximum number of iterations
        tolerance = 0.001 # TODO: Set the tolerance for the L1 norm of the `error`

        cost_l = []
        for _ in range(max_iterations):
            grad = gradient(theta)

            # Update the theta (parameters) using the gradient and the learning rate
            ################################################################################################
            # TODO: Implement the gradient update
            # TODO (BONUS): Implement the (quasi-)Newton's method for faster convergence

            theta -= learning_rate * grad
            ################################################################################################

            cost, l1 = cost_function(theta)
            # cost_l.append(cost)
            if l1.mean() < tolerance:
                break

        # print(f' \n COST: {cost} \n ')

        return theta

    def interpolate_triangle(self, t):
        # Intepolate between the three triangle positions in the self.ee_triangle_positions
        # based on the current time t
        ################################################################################################
        t_norm = t % 3.0

        if 0 <= t_norm < 1:
            # print("touchdown to liftoff")
            x_interp = np.interp(t_norm, [0, 1], 
                [self.ee_triangle_positions[0][0], self.ee_triangle_positions[1][0]])
            y_interp = np.interp(t_norm, [0, 1], 
                [self.ee_triangle_positions[0][1], self.ee_triangle_positions[1][1]])
            z_interp = np.interp(t_norm, [0, 1], 
                [self.ee_triangle_positions[0][2], self.ee_triangle_positions[1][2]])
        elif 1 <= t_norm < 2:
            # print("liftoff to mid-swing")
            x_interp = np.interp(t_norm, [1, 2], 
                [self.ee_triangle_positions[1][0], self.ee_triangle_positions[2][0]])
            y_interp = np.interp(t_norm, [1, 2], 
                [self.ee_triangle_positions[1][1], self.ee_triangle_positions[2][1]])
            z_interp = np.interp(t_norm, [1, 2], 
                [self.ee_triangle_positions[1][2], self.ee_triangle_positions[2][2]])
        elif 2<= t_norm < 3:
            # print("mid-swing to touchdown")
            x_interp = np.interp(t_norm, [2, 3], 
                [self.ee_triangle_positions[2][0], self.ee_triangle_positions[0][0]])
            y_interp = np.interp(t_norm, [2, 3], 
                [self.ee_triangle_positions[2][1], self.ee_triangle_positions[0][1]])
            z_interp = np.interp(t_norm, [2, 3], 
                [self.ee_triangle_positions[2][2], self.ee_triangle_positions[0][2]])

        target_interp = np.array([x_interp, y_interp, z_interp])

        # print(f"Time {t:.2f}: Position {target_interp}")

        return target_interp

        # vertex_time = np.array([0.0, 1/3, 2/3, 1.0])
        # x_pos = np.append(self.ee_triangle_positions[:, 0], self.ee_triangle_positions[0, 0])
        # y_pos = np.append(self.ee_triangle_positions[:, 1], self.ee_triangle_positions[0, 1])
        # z_pos = np.append(self.ee_triangle_positions[:, 2], self.ee_triangle_positions[0, 2])

        # x_lerp = np.interp(t_norm, key_)


    def ik_timer_callback(self):
        if self.joint_positions is not None:
            target_ee = self.interpolate_triangle(self.t)
            # print(target_ee)
            self.target_joint_positions = self.inverse_kinematics(target_ee, self.joint_positions)
            current_ee = self.forward_kinematics(*self.joint_positions)

            # update the current time for the triangle interpolation
            ################################################################################################
            # TODO: Implement the time update
            self.t += self.ik_timer_period * 2
            ################################################################################################
            
            self.get_logger().info(f'Target EE: {target_ee}, Current EE: {current_ee}, Target Angles: {self.target_joint_positions}, Target Angles to EE: {self.forward_kinematics(*self.target_joint_positions)}, Current Angles: {self.joint_positions}')

    def pd_timer_callback(self):
        if self.target_joint_positions is not None:

            command_msg = Float64MultiArray()
            command_msg.data = self.target_joint_positions.tolist()
            self.command_publisher.publish(command_msg)

def main():
    rclpy.init()
    inverse_kinematics = InverseKinematics()
    
    try:
        rclpy.spin(inverse_kinematics)
    except KeyboardInterrupt:
        print("Program terminated by user")
    finally:
        # Send zero torques
        zero_torques = Float64MultiArray()
        zero_torques.data = [0.0, 0.0, 0.0]
        inverse_kinematics.command_publisher.publish(zero_torques)
        
        inverse_kinematics.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
