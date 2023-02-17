练习
=====================

课后练习
--------------------------
编程题
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
3. \*** 扩展内核，支持基于缺页异常机制，具有Lazy 策略的按需分页机制。

   在页面懒分配（Lazy allocation of pages）技术中，内存分配并不会立即发生，而是在需要使用内存时才分配，这样可以节省系统的资源并提高程序的性能。

   实现页面懒分配的思路是：当调用sbrk时不分配实际的页面，而是仅仅增大堆的大小，当实际访问页面时，就会触发缺页异常，此时再申请一个页面并映射到页表中，这时再次执行触发缺页异常的代码就可以正常读写内存了。

   注释掉growproc()函数，增加堆的size，但不实际分配内存：

.. code-block:: c

   //os/syscall.c

   uint64 sys_sbrk(int n)
   {
        uint64 addr;
        struct proc *p = curr_proc();
        addr = p->program_brk;
        int heap_size = addr + n - p->heap_bottom; 
        if(heap_size < 0){
                errorf("out of heap_bottom\n");
                return -1;
        }
        else{
                p->program_brk += n; //增加堆的size，但不实际分配内存
                if(n < 0){
                        printf("uvmdealloc\n");
                        uvmdealloc(p->pagetable, addr, addr + n); //如果减少内存则调用内存释放函数
                }
        }
        //if(growproc(n) < 0) //注释掉growproc()函数，不实际分配内存
        //        return -1;
        return addr;
   }

因为没有给虚拟地址实际分配内存，所以当对相应的虚拟地址的内存进行读写的时候会触发缺页错误，这时再实际分配内存：

.. code-block:: c

   //os/loader.c
   
   void usertrap()
   {
        set_kerneltrap();
        struct trapframe *trapframe = curr_proc()->trapframe;
        tracef("trap from user epc = %p", trapframe->epc);
        if ((r_sstatus() & SSTATUS_SPP) != 0)
                panic("usertrap: not from user mode");

        uint64 cause = r_scause();
        if (cause & (1ULL << 63)) {
                cause &= ~(1ULL << 63);
                switch (cause) {
                case SupervisorTimer:
                        tracef("time interrupt!");
                        set_next_timer();
                        yield();
                        break;
                default:
                        unknown_trap();
                        break;
                }
        } else {
                switch (cause) {
                case UserEnvCall:
                        trapframe->epc += 4;
                        syscall();
                        break;
                case StorePageFault: // 读缺页错误
                case LoadPageFault:  // 写缺页错误
                        {
                                uint64 addr = r_stval(); // 获取发生缺页错误的地址
                                if(lazy_alloc(addr) < 0){ // 调用页面懒分配函数
                                        errorf("lazy_aolloc() failed!\n");
                                        exit(-2);
                                }
                                break;
                        }
                case StoreMisaligned:
                case InstructionMisaligned:
                case InstructionPageFault:
                case LoadMisaligned:
                        errorf("%d in application, bad addr = %p, bad instruction = %p, "
                               "core dumped.",
                               cause, r_stval(), trapframe->epc);
                        exit(-2);
                        break;
                case IllegalInstruction:
                        errorf("IllegalInstruction in application, core dumped.");
                        exit(-3);
                        break;
                default:
                        unknown_trap();
                        break;
                }
        }
        usertrapret();
   }
   
实现页面懒分配函数，首先判断地址是否在堆的范围内，然后分配实际的内存，最后在页面中建立映射：

.. code-block:: c

   //os/trap.c
   int lazy_alloc(uint64 addr){
        struct proc *p = curr_proc();

        // 通过两个if判断发生缺页错误的地址是否在堆的范围内，不在则返回
        if (addr >= p->program_brk) { 
                errorf("lazy_alloc: access invalid address");
                return -1;
        }

        if (addr < p->heap_bottom) {
                errorf("lazy_alloc: access address below stack");
                return -2;
        }

        uint64 va = PGROUNDDOWN(addr);
        char* mem = kalloc(); // 调用kalloc()实际分配页面
        if (mem == 0) {
                errorf("lazy_alloc: kalloc failed");
                return -3;
        }

        memset(mem, 0, PGSIZE);
        if(mappages(p->pagetable, va, PGSIZE, (uint64)mem, PTE_W|PTE_X|PTE_R|PTE_U) != 0){ // 将新分配的页面和虚拟地址在页表中建立映射
                kfree(mem);
                return -4;
        }
        return 0;
   }