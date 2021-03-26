from manimlib.imports import *

class Test(Scene):
    CONFIG = {
        "camera_config": {
            "background_color": WHITE,
        },
    }
    def construct(self):
        left_line = Line(start = np.array([-1, -4, 0]), end = np.array([-1, 4, 0]))
        left_line.set_color(BLACK)
        self.add(left_line)
        right_line = Line(start = np.array([1, -4, 0]), end = np.array([1, 4, 0]))
        right_line.set_color(BLACK)
        self.add(right_line)
        STACKFRAME_HEIGHT = 1.0
        STACKFRAME_WIDTH = 2.0
        for i in range(0, 4):
            stack_frame = Rectangle(height=1.0, width=2.0, stroke_color=BLACK, stroke_width=5, stroke_opacity=0.1)
            stack_frame.set_y(i * STACKFRAME_HEIGHT - 1)
            self.add(stack_frame)
            left_text = TextMobject("sp + %d" % (8*i,))
            left_text.next_to(stack_frame, LEFT)
            left_text.set_color(BLACK)
            self.add(left_text)

        high_address = TextMobject("High Address", color=BLUE)
        #high_address.to_corner(UL, buff=0.5)
        high_address.to_edge(TOP, buff=0).shift(RIGHT*(STACKFRAME_WIDTH+1))
        self.add(high_address)
        self.add(DashedLine(color=BLACK).next_to(high_address, LEFT, buff=0))
        low_address = TextMobject("Low Address", color=BLUE)
        low_address.to_edge(BOTTOM, buff=0).shift(RIGHT*(STACKFRAME_WIDTH+1))
        self.add(low_address)
        self.add(DashedLine(color=BLACK).next_to(low_address, LEFT, buff=0))

class CallStack(Scene):
    CONFIG = {
        "camera_config": {
            "background_color": WHITE,
        },
    }
    def construct(self):
        # constants
        BLOCK_WIDTH = 1
        BLOCK_TOP = 2
        HORIZONTAL_GAP = 1
        ADDR_ARROW_LENGTH = 1.5

        left_line = Line(np.array([-0.5, -3, 0]), np.array([-0.5, 3, 0]), color=BLACK)
        right_line = Line(np.array([0.5, -3, 0]), np.array([0.5, 3, 0]), color=BLACK)

        high_addr = TextMobject("High Address", color=BLACK).scale(0.7).move_to(np.array([5, 3, 0]), LEFT)
        low_addr = TextMobject("Low Address", color=BLACK).scale(0.7).move_to(np.array([5, -3, 0]), LEFT)
        addr_arrow = Arrow(color=BLACK, stroke_width=3) \
            .rotate(angle=90 * DEGREES, axis=IN).move_to(np.array([5.5, 0, 0])) \
            .scale(3.5)
        addr_arrow.add(
            TextMobject("grow", color=BLACK)
            .next_to(addr_arrow.get_center(), RIGHT, buff=0.1)
            .scale(0.7)
        )
        self.add(high_addr, low_addr, addr_arrow)

        stack_frame_a = Rectangle(width=BLOCK_WIDTH, height=1.5, stroke_color=BLACK)
        stack_frame_a.set_fill(color=BLUE, opacity=0.8)
        stack_frame_a.add(TextMobject("a", color=BLACK))
        stack_frame_a.shift(UP*BLOCK_TOP)
        stack_frame_b = Rectangle(width=BLOCK_WIDTH, height=1, stroke_color=BLACK)
        stack_frame_b.set_fill(color=RED, opacity=0.8)
        stack_frame_b.add(TextMobject("b", color=BLACK))
        stack_frame_b.next_to(stack_frame_a, DOWN, buff=0)
        stack_frame_c = Rectangle(width=BLOCK_WIDTH, height=2, stroke_color=BLACK)
        stack_frame_c.set_fill(color=GREEN, opacity=0.8)
        stack_frame_c.add(TextMobject("c", color=BLACK))
        stack_frame_c.next_to(stack_frame_b, DOWN, buff=0)
        vgroup_a = VGroup(left_line, right_line, stack_frame_a)
        vgroup_ab = vgroup_a.deepcopy().add(stack_frame_b)
        vgroup_abc = vgroup_ab.deepcopy().add(stack_frame_c)
        horizontal_group = [vgroup_a, vgroup_ab, vgroup_abc, vgroup_ab.deepcopy(), vgroup_a.deepcopy()]
        labels = [
            "Call a",
            "Call b",
            "Call c",
            "c returned",
            "b returned",
        ]
        for i in range(0, 5):
            # 0->2, 1->3, 2->4, 3->3, 4->2
            m = {0: 2, 1: 3, 2: 4, 3: 3, 4: 2}
            arrow = Arrow(color=BLACK).scale(0.25)
            arrow.next_to(horizontal_group[i][m[i]].get_corner(DL), LEFT, buff=0)
            arrow.add(TextMobject("sp", color=BLACK).next_to(arrow.get_left(), LEFT, buff=0).scale(0.7))
            label = TextMobject(labels[i], color=BLACK).scale(0.7).to_edge(TOP, buff=0.1)
            horizontal_group[i].add(arrow, label)

            horizontal_group[i].shift((i - 2) * (BLOCK_WIDTH + HORIZONTAL_GAP) * RIGHT)
            self.add(horizontal_group[i])

class StackFrame(Scene):
    CONFIG = {
        "camera_config": {
            "background_color": WHITE,
        },
    }
    def construct(self):
        # constants
        STACK_HEIGHT_HALF = 3.5
        left_line = Line(np.array([-1, -STACK_HEIGHT_HALF, 0]), np.array([-1, STACK_HEIGHT_HALF, 0]), color=BLACK)
        right_line = Line(np.array([1, -STACK_HEIGHT_HALF, 0]), np.array([1, STACK_HEIGHT_HALF, 0]), color=BLACK)
        self.add(left_line, right_line)
        father_stack_frame = Rectangle(width=2, height=1.5, fill_color=BLUE, fill_opacity=1.0).set_y(2.3)
        father_stack_frame.set_stroke(color=BLACK)

        father_stack_frame.add(TextMobject("Father", color=BLACK).scale(0.5).next_to(father_stack_frame.get_center(), UP, buff=0.1))
        father_stack_frame.add(TextMobject("StackFrame", color=BLACK).scale(0.5)\
            .next_to(father_stack_frame[1], DOWN, buff=0.2))

        ra = Rectangle(width=2, height=0.7, fill_color=YELLOW_E, fill_opacity=1.0).next_to(father_stack_frame, DOWN, buff=0)
        ra.set_stroke(color=BLACK)
        ra.add(TextMobject("ra", color=BLACK).scale(0.5).move_to(ra))

        fp = Rectangle(width=2, height=0.7, fill_color=TEAL_E, fill_opacity=1.0).next_to(ra, DOWN, buff=0)
        fp.set_stroke(color=BLACK)
        fp.add(TextMobject("prev fp", color=BLACK).scale(0.5).move_to(fp))

        callee_saved = Rectangle(width=2, height=1.3, fill_color=ORANGE, fill_opacity=1.0).next_to(fp, DOWN, buff=0)
        callee_saved.set_stroke(color=BLACK)
        callee_saved.add(TextMobject("Callee-saved", color=BLACK).scale(0.5).move_to(callee_saved))

        local_var = Rectangle(width=2, height=1.6, fill_color=MAROON_E, fill_opacity=0.7).next_to(callee_saved, DOWN, buff=0)
        local_var.set_stroke(color=BLACK)
        local_var.add(TextMobject("Local Variables", color=BLACK).scale(0.5).move_to(local_var))

        current_sp = Arrow(color=BLACK).next_to(local_var.get_corner(DL), LEFT, buff=0).scale(0.25, about_edge=RIGHT)
        current_sp.add(TextMobject("sp", color=BLACK).scale(0.5).next_to(current_sp.get_left(), LEFT, buff=0.1))

        current_fp = Arrow(color=BLACK).next_to(father_stack_frame.get_corner(DL), LEFT, buff=0).scale(.25, about_edge=RIGHT)
        current_fp.add(TextMobject("fp", color=BLACK).scale(0.5).next_to(current_fp.get_left(), LEFT, buff=0.1))

        upper_bound = Arrow(color=BLACK)\
            .rotate(90*DEGREES, IN)\
            .next_to(ra.get_corner(UR), DOWN, buff=0)\
            .shift(0.3*RIGHT)\
            .scale(1.2, about_edge=UP)\
            .set_stroke(width=3)
        upper_bound.tip.scale(0.4, about_edge=UP)
        lower_bound = Arrow(color=BLACK)\
            .rotate(90*DEGREES, OUT)\
            .next_to(local_var.get_corner(DR), UP, buff=0)\
            .shift(0.3*RIGHT)\
            .scale(1.2, about_edge=DOWN)\
            .set_stroke(width=3)
        lower_bound.tip.scale(0.4, about_edge=DOWN)
        current_stack_frame = TextMobject("Current StackFrame", color=BLACK).scale(0.5)\
            .next_to((upper_bound.get_center()+lower_bound.get_center())*.5, RIGHT, buff=0.1)
        upper_dash = DashedLine(color=BLACK).next_to(ra.get_corner(UR), RIGHT, buff=0)\
            .scale(0.7, about_edge=LEFT)
        lower_dash = DashedLine(color=BLACK).next_to(local_var.get_corner(DR), RIGHT, buff=0)\
            .scale(0.7, about_edge=LEFT)

        prev_fp_p1 = DashedLine(fp[1].get_right() + np.array([0.1, 0, 0]), fp[1].get_right() + np.array([1.2, 0, 0]), color=RED)
        delta_y = father_stack_frame.get_top()[1] - prev_fp_p1.get_right()[1]
        prev_fp_p2 = DashedLine(prev_fp_p1.get_right(), prev_fp_p1.get_right()+delta_y*UP, color=RED)
        prev_fp_p3 = DashedLine(prev_fp_p2.get_end(), father_stack_frame.get_corner(UR), color=RED)
        prev_fp_p3.add_tip(0.1)

        self.add(father_stack_frame, ra, fp, callee_saved, local_var, current_sp, current_fp)
        self.add(upper_bound, lower_bound, current_stack_frame, upper_dash, lower_dash)
        self.add(prev_fp_p1, prev_fp_p2, prev_fp_p3)

class MemoryLayout(Scene):
    CONFIG = {
        "camera_config": {
            "background_color": WHITE,
        },
    }
    def construct(self):
        # constants
        STACK_HEIGHT_HALF = 4
        left_line = Line(np.array([-1, -STACK_HEIGHT_HALF, 0]), np.array([-1, STACK_HEIGHT_HALF, 0]), color=BLACK)
        right_line = Line(np.array([1, -STACK_HEIGHT_HALF, 0]), np.array([1, STACK_HEIGHT_HALF, 0]), color=BLACK)
        self.add(left_line, right_line)

        text = Rectangle(width=2, height=1.5, stroke_color=BLACK).set_y(-3)
        #text.set_fill(color=GREEN, opacity=1.0)
        text.add(TextMobject(".text", color=BLACK).scale(0.7).move_to(text))
        rodata = Rectangle(width=2, height=.75, stroke_color=BLACK).next_to(text, UP, buff=0)
        rodata.add(TextMobject(".rodata", color=BLACK).scale(.7).move_to(rodata))
        data = Rectangle(width=2, height=.75, stroke_color=BLACK).next_to(rodata, UP, buff=0)
        #data.set_fill(color=TEAL_E, opacity=1.0)
        data.add(TextMobject(".data", color=BLACK).scale(0.7).move_to(data))
        bss = Rectangle(width=2, height=.75, stroke_color=BLACK).next_to(data, UP, buff=0)
        #bss.set_fill(color=MAROON_E, opacity=1.0)
        bss.add(TextMobject(".bss", color=BLACK).scale(0.7).move_to(bss))
        heap = Rectangle(width=2, height=1, stroke_color=BLACK).next_to(bss, UP, buff=0)
        #heap.set_fill(color=GRAY, opacity=1.0)
        heap.add(TextMobject("heap", color=BLACK).scale(0.7).move_to(heap))
        stack = Rectangle(width=2, height=1, stroke_color=BLACK).set_y(3)
        #stack.set_fill(color=BLUE_E, opacity=0.8)
        stack.add(TextMobject("stack", color=BLACK).scale(0.7).move_to(stack))
        stack_down = Arrow(color=BLACK).rotate(90*DEGREES, IN).next_to(stack, DOWN, buff=0)\
            .scale(0.35, about_edge=UP)
        stack_down.tip.scale(0.5, about_edge=UP)
        heap_up = Arrow(color=BLACK).rotate(90*DEGREES, OUT).next_to(heap, UP, buff=0)\
            .scale(0.35, about_edge=DOWN)
        heap_up.tip.scale(0.5, about_edge=DOWN)
        low_addr = TextMobject("Low Address", color=BLACK).to_edge(BOTTOM, buff=0.05).shift(3*RIGHT)
        high_addr = TextMobject("High Address", color=BLACK).to_edge(TOP, buff=.05).shift(3*RIGHT)

        division = DashedLine(color=BLACK).next_to(text.get_corner(UL), LEFT, buff=0).scale(1.5)
        data_mem_division = DashedLine(color=BLACK).next_to(stack.get_corner(UL), LEFT, buff=0).scale(1.5)
        code_mem_division = DashedLine(color=BLACK).next_to(text.get_corner(DL), LEFT, buff=0).scale(1.5)

        data_mem = TextMobject("Data Memory", color=BLACK).move_to((division.get_center()+data_mem_division.get_center())*.5)\
            .scale(.8)\
            .shift(LEFT*.3)
        code_mem = TextMobject("Code Memory", color=BLACK).move_to((division.get_center()+code_mem_division.get_center())*.5)\
            .scale(.8)\
            .shift(LEFT*.3)

        self.add(text, rodata, data, bss, heap, stack)
        self.add(stack_down, heap_up)
        self.add(low_addr, high_addr)
        self.add(division, data_mem_division, code_mem_division)
        self.add(data_mem, code_mem)




