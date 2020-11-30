from manimlib.imports import *

class EnvironmentCallFlow(Scene):
    CONFIG = {
        "camera_config": {
            "background_color": WHITE,
        },
    }
    def construct(self):
        os = Rectangle(height=FRAME_HEIGHT*.8, width=2.0, color=BLACK, fill_color=WHITE, fill_opacity=1.0)
        app = Rectangle(height=FRAME_HEIGHT*.8, width=2.0, color=BLACK, fill_color=WHITE, fill_opacity=1.0)
        app.shift(np.array([-4, 0, 0]))
        see = Rectangle(height=FRAME_HEIGHT*.8, width=2.0, color=BLACK, fill_color=WHITE, fill_opacity=1.0)
        see.shift(np.array([4, 0, 0]))
        self.add(os, app, see)
        os_text = TextMobject("OS", color=BLACK).next_to(os, UP, buff=0.2)
        app_text = TextMobject("Application", color=BLACK).next_to(app, UP, buff=0.2)
        see_text = TextMobject("SEE", color=BLACK).next_to(see, UP, buff=.2)
        self.add(os_text, app_text, see_text)
        app_ecall = Rectangle(height=0.5, width=2.0, color=BLACK, fill_color=BLUE, fill_opacity=1.0)
        app_ecall.move_to(app)
        app_ecall_text = TextMobject("ecall", color=BLACK).move_to(app_ecall)
        self.add(app_ecall, app_ecall_text)
        app_code1 = Rectangle(width=2.0, height=2.0, color=BLACK, fill_color=GREEN, fill_opacity=1.0)
        app_code1.next_to(app_ecall, UP, buff=0)
        self.add(app_code1)
        app_code2 = Rectangle(width=2.0, height=2.5, color=BLACK, fill_color=GREEN, fill_opacity=1.0)
        app_code2.next_to(app_ecall, DOWN, buff=0)
        self.add(app_code2)
        app_code1_text = TextMobject("U Code", color=BLACK).move_to(app_code1).shift(np.array([-.15, 0, 0]))
        app_code2_text = TextMobject("U Code", color=BLACK).move_to(app_code2).shift(np.array([-.15, 0, 0]))
        self.add(app_code1_text, app_code2_text)
        os_ecall = Rectangle(height=.5, width=2.0, color=BLACK, fill_color=BLUE, fill_opacity=1.0)
        os_ecall.move_to(os)
        os_ecall_text = TextMobject("ecall", color=BLACK).move_to(os_ecall)
        self.add(os_ecall, os_ecall_text)
        os_code1 = Rectangle(width=2.0, height=2.0, color=BLACK, fill_color=PURPLE, fill_opacity=1.0).next_to(os_ecall, UP, buff=0)
        os_code1_text = TextMobject("S Code", color=BLACK).move_to(os_code1).shift(np.array([-.15, 0, 0]))
        os_code2 = Rectangle(width=2.0, height=2.5, color=BLACK, fill_color=PURPLE, fill_opacity=1.0).next_to(os_ecall, DOWN, buff=0)
        os_code2_text = TextMobject("S Code", color=BLACK).move_to(os_code2).shift(np.array([-.15, 0, 0]))
        self.add(os_code1, os_code2, os_code1_text, os_code2_text)
        app_ecall_anchor = app_ecall.get_center() + np.array([0.8, 0, 0])
        app_front = Line(start=app_ecall_anchor+np.array([0, 2, 0]), end=app_ecall_anchor, color=RED)
        app_front.add_tip(tip_length=0.2)
        self.add(app_front)
        os_ecall_anchor = os_ecall.get_center() + np.array([0.8, 0, 0])
        os_front = Line(start=os_ecall_anchor+np.array([0, 2, 0]), end=os_ecall_anchor, color=RED)
        os_front.add_tip(tip_length=.2)
        self.add(os_front)
        trap_to_os = DashedLine(start=app_ecall_anchor, end=os_ecall_anchor+np.array([0, 2, 0]), color=RED)
        trap_to_os.add_tip(tip_length=.2)
        self.add(trap_to_os)
        see_entry = see.get_center()+np.array([0.8, 2, 0])
        see_exit = see_entry+np.array([0, -4, 0])
        see_code = Rectangle(width=2.0, height=see_entry[1]-see_exit[1], color=BLACK, fill_color=GRAY, fill_opacity=1.0).move_to(see)
        self.add(see_code)
        see_text = TextMobject("M Code", color=BLACK).move_to(see_code).shift(np.array([-.15, 0, 0]))
        self.add(see_text)
        see_front = Line(start=see_entry, end=see_exit, color=RED).add_tip(tip_length=.2)
        self.add(see_front)
        trap_to_see = DashedLine(start=os_ecall_anchor, end=see_entry, color=RED).add_tip(tip_length=.2)
        self.add(trap_to_see)
        os_back_anchor = os_ecall_anchor+np.array([0, -.5, 0])
        trap_back_to_os = DashedLine(start=see_exit, end=os_back_anchor, color=RED).add_tip(tip_length=.2)
        self.add(trap_back_to_os)
        os_exit = os_back_anchor+np.array([0, -2, 0])
        os_front2 = Line(start=trap_back_to_os, end=os_exit, color=RED).add_tip(tip_length=.2)
        self.add(os_front2)
        app_back_anchor = app_ecall_anchor+np.array([0, -.5, 0])
        trap_back_to_app = DashedLine(start=os_exit, end=app_back_anchor, color=RED).add_tip(tip_length=.2)
        self.add(trap_back_to_app)
        app_front2 = Line(start=app_back_anchor, end=app_back_anchor+np.array([0, -2, 0]), color=RED)
        app_front2.add_tip(tip_length=.2)
        self.add(app_front2)
        u_into_s = TextMobject("U into S", color=BLACK).next_to(app_ecall, RIGHT, buff=0).shift(np.array([0, .5, 0])).scale(0.5)
        s_back_u = TextMobject("S back to U", color=BLACK).next_to(app_ecall, RIGHT, buff=0).shift(np.array([-.3, -1, 0])).scale(0.5)
        s_into_m = TextMobject("S into M", color=BLACK).next_to(os_ecall, RIGHT, buff=0).shift(np.array([0, .5, 0])).scale(.5)
        m_back_s = TextMobject("M back to S", color=BLACK).next_to(os_ecall, RIGHT, buff=0).shift(np.array([-.3, -1, 0])).scale(.5)
        self.add(u_into_s, s_back_u, s_into_m, m_back_s)



class PrivilegeStack(Scene):
    CONFIG = {
        "camera_config": {
            "background_color": WHITE,
        },
    }
    def construct(self):
        os = Rectangle(width=4.0, height=1.0, color=BLACK, fill_color=WHITE, fill_opacity=1.0)
        os_text = TextMobject("OS", color=BLACK).move_to(os)
        self.add(os, os_text)

        sbi = Rectangle(width=4.0, height=1.0, color=BLACK, fill_color=BLACK, fill_opacity=1.0)
        sbi.next_to(os, DOWN, buff=0)
        sbi_text = TextMobject("SBI", color=WHITE).move_to(sbi)
        self.add(sbi, sbi_text)

        see = Rectangle(width=4.0, height=1.0, color=BLACK, fill_color=WHITE, fill_opacity=1.0)
        see.next_to(sbi, DOWN, buff=0)
        see_text = TextMobject("SEE", color=BLACK).move_to(see)
        self.add(see, see_text)

        abi0 = Rectangle(height=1.0, width=1.8, color=BLACK, fill_color=BLACK, fill_opacity=1.0)
        abi0.next_to(os, UP, buff=0).align_to(os, LEFT)
        abi0_text = TextMobject("ABI", color=WHITE).move_to(abi0)
        self.add(abi0, abi0_text)

        abi1 = Rectangle(height=1.0, width=1.8, color=BLACK, fill_color=BLACK, fill_opacity=1.0)
        abi1.next_to(os, UP, buff=0).align_to(os, RIGHT)
        abi1_text = TextMobject("ABI", color=WHITE).move_to(abi1)
        self.add(abi1, abi1_text)

        app0 = Rectangle(height=1.0, width=1.8, color=BLACK, fill_color=WHITE, fill_opacity=1.0)
        app0.next_to(abi0, UP, buff=0)
        app0_text = TextMobject("App", color=BLACK).move_to(app0)
        self.add(app0, app0_text)

        app1 = Rectangle(height=1.0, width=1.8, color=BLACK, fill_color=WHITE, fill_opacity=1.0)
        app1.next_to(abi1, UP, buff=0)
        app1_text = TextMobject("App", color=BLACK).move_to(app1)
        self.add(app1, app1_text)

        line0 = DashedLine(sbi.get_right(), sbi.get_right() + np.array([3, 0, 0]), color=BLACK)
        self.add(line0)
        line1 = DashedLine(abi1.get_right(), abi1.get_right() + np.array([3, 0, 0]), color=BLACK)
        self.add(line1)

        machine = TextMobject("Machine", color=BLACK).next_to(see, RIGHT, buff=.8)
        supervisor = TextMobject("Supervisor", color=BLACK).next_to(os, RIGHT, buff=.8)
        user = TextMobject("User", color=BLACK).next_to(app1, RIGHT, buff=.8)
        self.add(machine, supervisor, user)

