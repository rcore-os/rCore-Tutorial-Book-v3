练习
=====================

课后练习
--------------------------
编程题
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
7. \*** 扩展内核，支持基于缺页异常的COW机制。（初始时，两个任务共享一个只读物理页。当一个任务执行写操作后，两个任务拥有各自的可写物理页）

   COW（Copy on Write）是指当需要在内存中创建一个新的副本时，COW技术会推迟复制操作，直到数据被修改为止。从而减少不必要的内存拷贝，提升性能。

   实现COW的思路是：在创建内存副本时，在内存中创建一个指向原始数据的指针或引用，而不是创建原始数据的完整副本。如果原始数据没有被修改，新副本将继续共享原始数据的指针或引用，以节省内存。当某个程序试图修改数据时，COW技术会在新副本中复制原始数据，使得每个程序都有自己的独立副本，从而避免数据之间的干扰。

   增加一个当做计数器的数据结构用于记录每个物理页面被多少变量引用，当页面初始被分配时计数器设置为1，其后如果产生副本则计数器加1。当页面被释放的时候则计数器减1，如果计数器不为0，说明还有其他引用在使用该页面，此时不执行实际的释放操作，最后计数器变为0时才真正释放页面：

.. code-block:: c

   //os/kalloc.c
   uint64 page_ref[ (PHYSTOP - KERNBASE)/PAGE_SIZE] = {0}; // 定义用来记录页面引用的计数器，并将其值初始化为0

   // 新增修改页面计数器的函数
   void page_ref_add(uint64 pa, int n){ // 增加页面计数
        page_ref[(PGROUNDDOWN(pa)-KERNBASE)/PGSIZE] += n;
   }

   void page_ref_reduce(uint64 pa, int n){ // 减少页面计数
        page_ref[(PGROUNDDOWN(pa)-KERNBASE)/PGSIZE] -= n;
   }

   uint64 page_ref_get(uint64 pa){ // 返回页面计数
        return page_ref[(PGROUNDDOWN(pa)-KERNBASE)/PGSIZE];
   }

   void *kalloc()
   {
        struct linklist *l;
        l = kmem.freelist;
        if (l) {
                kmem.freelist = l->next;
                memset((char *)l, 5, PGSIZE); // fill with junk
                page_ref_add((uint64)l, 1); // 在页面分配的时候设置计数器为1
        }
        return (void *)l;
   }

   void kfree(void *pa)
   {
        struct linklist *l;
        if (((uint64)pa % PGSIZE) != 0 || (char *)pa < ekernel ||
            (uint64)pa >= PHYSTOP)
                panic("kfree");


        if(page_ref_get((uint64)pa) > 1){ // 判断计数器的值，如果大于1说明还有其他引用，计数器减1后直接返回
                page_ref_reduce((uint64)pa, 1);
                return;
        }

        // Fill with junk to catch dangling refs.
        memset(pa, 1, PGSIZE);
        l = (struct linklist *)pa;
        l->next = kmem.freelist;
        kmem.freelist = l;
   }

修改内存复制函数umcopy()，其实不进行实际的内存复制，只是增加新的引用到需要复制的内存上：

.. code-block:: c

   //os/vm.c

   int uvmcopy(pagetable_t old, pagetable_t new, uint64 max_page)
  {
        pte_t *pte;
        uint64 pa, i;
        uint flags;
        //char *mem;

        for (i = 0; i < max_page * PAGE_SIZE; i += PGSIZE) {
                if ((pte = walk(old, i, 0)) == 0)
                        continue;
                if ((*pte & PTE_V) == 0)
                        continue;
                pa = PTE2PA(*pte);
                flags = PTE_FLAGS(*pte);

                *pte = ((*pte) & (~PTE_W)) | PTE_COW; // 虽然不进行内存页的复制，但是需要修改内存页的操作权限，取消页的写操作权限，同时增加COW权限

                /*if ((mem = kalloc()) == 0) // 注释掉分配内存的函数
                        goto err;
                memmove(mem, (char *)pa, PGSIZE);

                if (mappages(new, i, PGSIZE, (uint64)mem, flags) != 0) {*/

                if (mappages(new, i, PGSIZE, (uint64)pa, (flags & (~PTE_W)) | PTE_COW) != 0) { // 让另一页表中的虚拟地址指向原来页表中的物理地址
                        //kfree(mem);
                        goto err;
                }
                page_ref_add(pa, 1);
        }
        return 0;

   err:
        uvmunmap(new, 0, i / PGSIZE, 1);
        return -1;
   }

因为没有实际地进行内存复制，且取消了页面的的写权限，所以当对相应的虚拟地址的内存进行写操作的时候会触发缺页错误，这时再调用cowcopy()函数实际分配页或修改页的写权限：

.. code-block:: c

   //os/trap.c
   
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
                case StorePageFault:{ // 写缺页错误
                        uint64 va = r_stval(); //获取发生缺页错误的虚拟地址
                        if(cowcopy(va) == -1){ // 当发生写缺页错误的时候，调用COW函数，进行实际的内存复制
                                errorf("Copy on Write Failed!\n");
                                exit(-2);
                        }
                        break;
                }
                case StoreMisaligned:
                case InstructionMisaligned:
                case InstructionPageFault:
                case LoadMisaligned:
                case LoadPageFault:
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
   
实现cowcopy()分配函数，首先判断地址是否在堆的范围内，然后分配实际的内存，最后在页面中建立映射：

.. code-block:: c

   //os/vm.c
   int cowcopy(uint64 va){
        va = PGROUNDDOWN(va);
        pagetable_t p = curr_proc()->pagetable;
        pte_t* pte = walk(p, va, 0);
        uint64 pa = PTE2PA(*pte);
        uint flags = PTE_FLAGS(*pte); // 获取页面的操作权限

        if(!(flags & PTE_COW)){
                printf("not cow\n");
                return -2; // not cow page
        }

        uint ref = page_ref_get(pa); // 获取页面的被引用的次数
        if(ref > 1){ // 若果大于1则说明有多个引用，这时需要重新分配页面
                // ref > 1, alloc a new page
                char* mem = kalloc();
                if(mem == 0){
                        errorf("kalloc failed!\n");
                        return -1;
                }
                memmove(mem, (char*)pa, PGSIZE); // 复制页中的内容到新的页
                if(mappages(p, va, PGSIZE, (uint64)mem, (flags & (~PTE_COW)) | PTE_W) != 0){
                        errorf("mappage failed!\n");
                        kfree(mem);
                        return -1;
                }
                page_ref_reduce(pa, 1);
        }else{
                // ref = 1, use this page directly
                *pte = ((*pte) & (~PTE_COW)) | PTE_W; // 如果没有其他引用则修改页面操作权限，使得该页面可以进行写操作
        }
        return 0;
   }