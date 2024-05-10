练习
=====================

课后练习
--------------------------
编程题
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
2. \*** 修改本章操作系统内核，实现任务和操作系统内核共用同一张页表的单页表机制。

   要实现任务和操作系统内核通用一张页表，需要了解清楚内核地址空间和任务地址空间的布局，然后为每个任务在内核地址空间中单独分配一定的地址空间。

   在描述任务的struct proc中添加新的成员“kpgtbl”、“trapframe_base”，前者用户保存内核页表，后者用于保存任务的TRAPFRAME虚地址。并增加获取内核页表的函数“get_kernel_pagetable()”。

.. code-block:: c

   //os/proc.h

   struct proc {
        enum procstate state; // Process state
        int pid; // Process ID
        pagetable_t pagetable; // User page table
        uint64 ustack;
        uint64 kstack; // Virtual address of kernel stack
        struct trapframe *trapframe; // data page for trampoline.S
        struct context context; // swtch() here to run process
        uint64 max_page;
        uint64 program_brk;
        uint64 heap_bottom;
        pagetable_t kpgtbl; // 增加kpgtbl，用于保存内核页表
        uint64 trapframe_base; // 增加trapframe，用于保存任务自己的trapframe
   }

   //os/vm.c

   //增加get_kernel_pagetable函数，返回内核页表
   pagetable_t get_kernel_pagetable(){
        return kernel_pagetable;
   }

让任务使用内核页表，在内核地址空间中为每个任务分配一定的地址空间，在bin_loader()函数中修改任务的内存布局。

.. code-block:: c

   //os/loader.c
   //修改任务的地址空间
   pagetable_t bin_loader(uint64 start, uint64 end, struct proc *p, int num)
   {
        //pagetable_t pg = uvmcreate(); //任务不创建自己的页表
        pagetable_t pg = get_kernel_pagetable(); //获取内核页表
        uint64 trapframe = TRAPFRAME - (num + 1)* PAGE_SIZE; // 为每个任务依次指定TRAPFRAME
        if (mappages(pg, trapframe, PGSIZE, (uint64)p->trapframe,
                     PTE_R | PTE_W) < 0) {
                panic("mappages fail");
        }
        if (!PGALIGNED(start)) {
                panic("user program not aligned, start = %p", start);
        }
        if (!PGALIGNED(end)) {
                // Fix in ch5
                warnf("Some kernel data maybe mapped to user, start = %p, end = %p",
                      start, end);
        }
        end = PGROUNDUP(end);
        uint64 length = end - start;
        uint64 base_address = BASE_ADDRESS + (num * (p->max_page + 100)) * PAGE_SIZE; //设置任务的起始地址，并为任务保留100个页用做堆内存
        if (mappages(pg, base_address, length, start,
                     PTE_U | PTE_R | PTE_W | PTE_X) != 0) {
                panic("mappages fail");
        }
        p->pagetable = pg;
        uint64 ustack_bottom_vaddr = base_address + length + PAGE_SIZE;
        if (USTACK_SIZE != PAGE_SIZE) {
                // Fix in ch5
                panic("Unsupported");
        }
        mappages(pg, ustack_bottom_vaddr, USTACK_SIZE, (uint64)kalloc(),
                 PTE_U | PTE_R | PTE_W | PTE_X);
        p->ustack = ustack_bottom_vaddr;
        p->trapframe->epc = base_address;
        p->trapframe->sp = p->ustack + USTACK_SIZE;
        p->max_page = PGROUNDUP(p->ustack + USTACK_SIZE - 1) / PAGE_SIZE;
        p->program_brk = p->ustack + USTACK_SIZE;
        p->heap_bottom = p->ustack + USTACK_SIZE;
        p->trapframe_base = trapframe; //任务保存自己的TRAPFRAME
        return pg;
   }
   
在内核返回任务中使用任务自己的TRAPFRAME。

.. code-block:: c

   //os/trap.c
   void usertrapret()
   {
        set_usertrap();
        struct trapframe *trapframe = curr_proc()->trapframe;
        trapframe->kernel_satp = r_satp(); // kernel page table
        trapframe->kernel_sp =
                curr_proc()->kstack + KSTACK_SIZE; // process's kernel stack
        trapframe->kernel_trap = (uint64)usertrap;
        trapframe->kernel_hartid = r_tp(); // unuesd

        w_sepc(trapframe->epc);
        // set up the registers that trampoline.S's sret will use
        // to get to user space.

        // set S Previous Privilege mode to User.
        uint64 x = r_sstatus();
        x &= ~SSTATUS_SPP; // clear SPP to 0 for user mode
        x |= SSTATUS_SPIE; // enable interrupts in user mode
        w_sstatus(x);

        // tell trampoline.S the user page table to switch to.
        uint64 satp = MAKE_SATP(curr_proc()->pagetable);
        uint64 fn = TRAMPOLINE + (userret - trampoline);
        tracef("return to user @ %p", trapframe->epc);
        ((void (*)(uint64, uint64))fn)(curr_proc()->trapframe_base, satp); //使用任务自己的TRAPFRAME
        //((void (*)(uint64, uint64))fn)(TRAPFRAME, satp);
   }