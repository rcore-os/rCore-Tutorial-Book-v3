练习参考答案
============================================

课后练习
-------------------------------

编程题
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. `**` 使用sbrk，mmap,munmap,mprotect内存相关系统调用的linux应用程序。

   可以编写使用sbrk系统调用的应用程序，具体代码如下：

.. code-block:: c

   //user/src/ch4_sbrk.c
   int main()
   {
            printf("Test sbrk start.\n");
            uint64 PAGE_SIZE = 0x1000;
            uint64 origin_brk = sbrk(0);
            printf("origin break point = %p\n", origin_brk);
            uint64 brk = sbrk(PAGE_SIZE);
            if(brk != origin_brk){
                    return -1;
            }
            brk = sbrk(0);
            printf("one page allocated, break point = %p\n", brk);
            printf("try write to allocated page\n");
            char *new_page = (char *)origin_brk;
            for(uint64 i = 0;i < PAGE_SIZE;i ++) {
                    new_page[i] = 1;
            }
            printf("write ok\n");
            sbrk(PAGE_SIZE * 10);
            brk = sbrk(0);
            printf("10 page allocated, break point = %p\n", brk);
            sbrk(PAGE_SIZE * -11);
            brk = sbrk(0);
            printf("11 page DEALLOCATED, break point = %p\n", brk);
            printf("try DEALLOCATED more one page, should be failed.\n");
            uint64 ret = sbrk(PAGE_SIZE * -1);
            if(ret != -1){
                    printf("Test sbrk failed!\n");
                    return -1;
            }
            printf("Test sbrk almost OK!\n");
            printf("now write to deallocated page, should cause page fault.\n");
            for(uint64 i = 0;i < PAGE_SIZE;i ++){
                    new_page[i] = 2;
            }
            return 0;
    }

使用mmap、unmap系统调用的应用代码可参考测例中的ch4_mmap0.c、ch4_unmap0.c等代码。

2. `***` 修改本章操作系统内核，实现任务和操作系统内核共用同一张页表的单页表机制。

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

3. `***` 扩展内核，支持基于缺页异常机制，具有Lazy 策略的按需分页机制。


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

4. `***` 扩展内核，支持基于缺页异常的COW机制。（初始时，两个任务共享一个只读物理页。当一个任务执行写操作后，两个任务拥有各自的可写物理页）

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

5. `***` 扩展内核，实现swap in/out机制，并实现Clock置换算法或二次机会置换算法。
6. `***` 扩展内核，实现自映射机制。

问答题
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. chyyuu   这次的实验没有涉及到缺页有点遗憾，主要是缺页难以测试，而且更多的是一种优化，不符合这次实验的核心理念，所以这里补两道小题。

1. `*` 在使用高级语言编写用户程序的时候，手动用嵌入汇编的方法随机访问一个不在当前程序逻辑地址范围内的地址，比如向该地址读/写数据。该用户程序执行的时候可能会生什么？ 

   可能会报出缺页异常.

2. `*` 用户程序在运行的过程中，看到的地址是逻辑地址还是物理地址？从用户程序访问某一个地址，到实际内存中的对应单元被读/写，会经过什么样的过程，这个过程中操作系统有什么作用？（站在学过计算机组成原理的角度）

   逻辑地址。这个过程需要经过页表的转换，操作系统会负责建立页表映射。实际程序执行时的具体VA到PA的转换是在CPU的MMU之中进行的。

3. `*` 覆盖、交换和虚拟存储有何异同，虚拟存储的优势和挑战体现在什么地方？

   它们都是采取层次存储的思路，将暂时不用的内存放到外存中去，以此来缓解内存不足的问题。

   不同之处：覆盖是程序级的，需要程序员自行处理。交换则不同，由OS控制交换程序段。虚拟内存也由OS和CPU来负责处理，可以实现内存交换到外存的过程。
   
   虚拟存储的优势:1.与段/页式存储完美契合，方便非连续内存分配。2.粒度合适，比较灵活。兼顾了覆盖和交换的好处：可以在较小粒度上置换；自动化程度高，编程简单，受程序本身影响很小。（覆盖的粒度受限于程序模块的大小，对编程技巧要求很高。交换粒度较大，受限于程序所需内存。尤其页式虚拟存储，几乎不受程序影响，一般情况下，只要置换算法合适，表现稳定、高效）3.页式虚拟存储还可以同时消除内存外碎片并将内碎片限制在一个页面大小以内，提高空间利用率。
   
   虚拟存储的挑战: 1.依赖于置换算法的性能。2.相比于覆盖和交换，需要比较高的硬件支持。3.较小的粒度在面临大规模的置换时会发生多次较小规模置换，降低效率。典型情况是程序第一次执行时的大量page fault，可配合预取技术缓解这一问题。

4. `*` 什么是局部性原理？为何很多程序具有局部性？局部性原理总是正确的吗？为何局部性原理为虚拟存储提供了性能的理论保证？

   局部性分时间局部性和空间局部性（以及分支局部性）。局部性的原理是程序经常对一块相近的地址进行访问或者是对一个范围内的指令进行操作。局部性原理不一定是一直正确的。虚拟存储以页为单位，局部性使得数据和指令的访存局限在几页之中，可以避免页的频繁换入换出的开销，同时也符合TLB和cache的工作机制。

5. `**` 一条load指令，最多导致多少次页访问异常？尝试考虑较多情况。

   考虑多级页表的情况。首先指令和数据读取都可能缺页。因此指令会有3次访存，之后的数据读取除了页表页缺失的3次访存外，最后一次还可以出现地址不对齐的异常，因此可以有7次异常。若考更加极端的情况，也就是页表的每一级都是不对齐的地址并且处在两页的交界处（straddle），此时一次访存会触发2次读取页面，如果这两页都缺页的话，会有更多的异常次数。

6. `**` 如果在页访问异常中断服务例程执行时，再次出现页访问异常，这时计算机系统（软件或硬件）会如何处理？这种情况可能出现吗？

   我们实验的os在此时不支持内核的异常中断，因此此时会直接panic掉，并且这种情况在我们的os中这种情况不可能出现。像linux系统，也不会出现嵌套的page fault。

7. `*` 全局和局部置换算法有何不同？分别有哪些算法？

   全局页面置换算法：可动态调整某任务拥有的物理内存大小；影响其他任务拥有的物理内存大小。例如：工作集置换算法，缺页率置换算法。

   局部页面置换算法：每个任务分配固定大小的物理页，不会动态调整任务拥有的物理页数量；只考虑单个任务的内存访问情况，不影响其他任务拥有的物理内存。例如：最优置换算法、FIFO置换算法、LRU置换算法、Clock置换算法。

8. `*` 简单描述OPT、FIFO、LRU、Clock、LFU的工作过程和特点 (不用写太多字，简明扼要即可)

   OPT：选择一个应用程序在随后最长时间内不会被访问的虚拟页进行换出。性能最佳但无法实现。
   
   FIFO：由操作系统维护一个所有当前在内存中的虚拟页的链表，从交换区最新换入的虚拟页放在表尾，最久换入的虚拟页放在表头。当发生缺页中断时，淘汰/换出表头的虚拟页并把从交换区新换入的虚拟页加到表尾。实现简单，对页访问的局部性感知不够。
   
   LRU：替换的是最近最少使用的虚拟页。实现相对复杂，但考虑了访存的局部性，效果接近最优置换算法。
   
   Clock：将所有有效页放在一个环形循环列表中，指针根据页表项的使用位（0或1）寻找被替换的页面。考虑历史访问，性能略差于但接近LRU。
   
   LFU：当发生缺页中断时，替换访问次数最少的页面。只考虑访问频率，不考虑程序动态运行。

9.  `**` 综合考虑置换算法的收益和开销，综合评判在哪种程序执行环境下使用何种算法比较合适？

   FIFO算法：在内存较小的系统中，FIFO 算法可能是一个不错的选择，因为它的实现简单，开销较小，但是会存在 Belady 异常。
   
   LRU算法：在内存容量较大、应用程序具有较强的局部性时，LRU 算法可能是更好的选择，因为它可以充分利用页面的访问局部性，且具有较好的性能。

   Clock算法：当应用程序中存在一些特殊的内存访问模式时，例如存在循环引用或者访问模式具有周期性时，Clock 算法可能会比较适用，因为它能够处理页面的访问频率。

   LFU算法：对于一些需要对内存访问进行优先级调度的应用程序，例如多媒体应用程序，LFU 算法可能是更好的选择，因为它可以充分考虑页面的访问频率，对重要性较高的页面进行保护，但是实现比较复杂。

10. `**` Clock算法仅仅能够记录近期是否访问过这一信息，对于访问的频度几乎没有记录，如何改进这一点？

   如果想要改进这一点，可以将Clock算法和计数器结合使用。具体做法是为每个页面设置一个计数器，记录页面在一段时间内的访问次数，然后在置换页面时，既考虑页面最近的访问时间，也考虑其访问频度。当待缓存对象在缓存中时，把其计数器的值加1。同时，指针指向该对象的下一个对象。若不在缓存中时，检查指针指向对象的计数器。如果是0，则用待缓存对象替换该对象；否则，把计数器的值减1，指针指向下一个对象。如此直到淘汰一个对象为止。由于计数器的值允许大于1，所以指针可能循环多遍才淘汰一个对象。

11. `***` 哪些算法有belady现象？思考belady现象的成因，尝试给出说明OPT和LRU等为何没有belady现象。

   FIFO算法、Clock算法。

   页面调度算法可分为堆栈式和非堆栈式，LRU、LFU、OPT均为堆栈类算法，FIFO、Clock为非堆栈类算法，只有非堆栈类才会出现Belady现象。

12. `*` 什么是工作集？什么是常驻集？简单描述工作集算法的工作过程。

   工作集为一个进程当前正在使用的逻辑页面集合，可表示为二元函数$W(t, \Delta)$，t 为执行时刻，$\Delta$ 称为工作集窗口，即一个定长的页面访问时间窗口，$W(t, \Delta)$是指在当前时刻 t 前的 $\Delta$ 时间窗口中的所有访问页面所组成的集合，$|W(t, \Delta)|$为工作集的大小，即页面数目。

13. `*` 请列举 SV39 页`*` 页表项的组成，结合课堂内容，描述其中的标志位有何作用／潜在作用？

   [63:54]为保留项，[53:10]为44位物理页号，最低的8位[7:0]为标志位。

   - V(Valid)：仅当位 V 为 1 时，页表项才是合法的；
   - R(Read)/W(Write)/X(eXecute)：分别控制索引到这个页表项的对应虚拟页面是否允许读/写/执行；
   - U(User)：控制索引到这个页表项的对应虚拟页面是否在 CPU 处于 U 特权级的情况下是否被允许访问；
   - A(Accessed)：处理器记录自从页表项上的这一位被清零之后，页表项的对应虚拟页面是否被访问过；
   - D(Dirty)：处理器记录自从页表项上的这一位被清零之后，页表项的对应虚拟页面是否被修改过。

14. `**` 请问一个任务处理 10G 连续的内存页面，需要操作的页表实际大致占用多少内存(给出数量级即可)？

大致占用`10G/512=20M`内存。

15. `**`  缺页指的是进程访问页面时页面不在页表中或在页表中无效的现象，此时 MMU 将会返回一个中断，告知操作系统：该进程内存访问出了问题。然后操作系统可选择填补页表并重新执行异常指令或者杀死进程。操作系统基于缺页异常进行优化的两个常见策略中，其一是 Lazy 策略，也就是直到内存页面被访问才实际进行页表操作。比如，一个程序被执行时，进程的代码段理论上需要从磁盘加载到内存。但是 操作系统并不会马上这样做，而是会保存 .text 段在磁盘的位置信息，在这些代码第一次被执行时才完成从磁盘的加载操作。 另一个常见策略是 swap 页置换策略，也就是内存页面可能被换到磁盘上了，导致对应页面失效，操作系统在任务访问到该页产生异常时，再把数据从磁盘加载到内存。

    1. 哪些异常可能是缺页导致的？发生缺页时，描述与缺页相关的CSR寄存器的值及其含义。
  
    - 答案： `mcause` 寄存器中会保存发生中断异常的原因，其中 `Exception Code` 为 `12` 时发生指令缺页异常，为 `15` 时发生 `store/AMO` 缺页异常，为 `13` 时发生 `load` 缺页异常。

    CSR寄存器: 
        
       - `scause`: 中断/异常发生时， `CSR` 寄存器 `scause` 中会记录其信息， `Interrupt` 位记录是中断还是异常， `Exception Code` 记录中断/异常的种类。
       - `sstatus`: 记录处理器当前状态，其中 `SPP` 段记录当前特权等级。
       - `stvec`: 记录处理 `trap` 的入口地址，现有两种模式 `Direct` 和 `Vectored` 。
       - `sscratch`: 其中的值是指向hart相关的S态上下文的指针，比如内核栈的指针。
       - `sepc`: `trap` 发生时会将当前指令的下一条指令地址写入其中，用于 `trap` 处理完成后返回。
       - `stval`: `trap` 发生进入S态时会将异常信息写入，用于帮助处理 `trap` ，其中会保存导致缺页异常的虚拟地址。
 
    2. Lazy 策略有哪些好处？请描述大致如何实现Lazy策略？

    - 答案：Lazy策略一定不会比直接加载策略慢，并且可能会提升性能，因为可能会有些页面被加载后并没有进行访问就被释放或替代了，这样可以避免很多无用的加载。分配内存时暂时不进行分配，只是将记录下来，访问缺页时会触发缺页异常，在`trap handler`中处理相应的异常，在此时将内存加载或分配即可。
  
    3. swap 页置换策略有哪些好处？此时页面失效如何表现在页表项(PTE)上？请描述大致如何实现swap策略？

    - 答案：可以为用户程序提供比实际物理内存更大的内存空间。页面失效会将标志位`V`置为`0`。将置换出的物理页面保存在磁盘中，在之后访问再次触发缺页异常时将该页面写入内存。
  
16. `**` 为了防范侧信道攻击，本章的操作系统使用了双页表。但是传统的操作系统设计一般采用单页表，也就是说，任务和操作系统内核共用同一张页表，只不过内核对应的地址只允许在内核态访问。(备注：这里的单/双的说法仅为自创的通俗说法，并无这个名词概念，详情见 `KPTI <https://en.wikipedia.org/wiki/Kernel_page-table_isolation>`_ )

    1. 单页表情况下，如何控制用户态无法访问内核页面？
  
    - 答案：将内核页面的 pte 的`U`标志位设置为0。
 
    2. 相对于双页表，单页表有何优势？
 
    - 答案：在内核和用户态之间转换时不需要更换页表，也就不需要跳板，可以像之前一样直接切换上下文。
 
    3. 请描述：在单页表和双页表模式下，分别在哪个时机，如何切换页表？
 
    - 答案：双页表实现下用户程序和内核转换时、用户程序转换时都需要更换页表，而对于单页表操作系统，不同用户线程切换时需要更换页表。

实验练习
-------------------------------

实验练习包括实践作业和问答作业两部分。

实践作业
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

重写 sys_get_time
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

引入虚存机制后，原来内核的 sys_get_time 函数实现就无效了。请你重写这个函数，恢复其正常功能。

mmap 和 munmap 匿名映射
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

`mmap <https://man7.org/linux/man-pages/man2/mmap.2.html>`_ 在 Linux 中主要用于在内存中映射文件，本次实验简化它的功能，仅用于申请内存。

请实现 mmap 和 munmap 系统调用，mmap 定义如下：


.. code-block:: rust

    fn sys_mmap(start: usize, len: usize, prot: usize) -> isize

- syscall ID：222
- 申请长度为 len 字节的物理内存（不要求实际物理内存位置，可以随便找一块），将其映射到 start 开始的虚存，内存页属性为 prot
- 参数：
    - start 需要映射的虚存起始地址，要求按页对齐
    - len 映射字节长度，可以为 0
    - prot：第 0 位表示是否可读，第 1 位表示是否可写，第 2 位表示是否可执行。其他位无效且必须为 0
- 返回值：执行成功则返回 0，错误返回 -1
- 说明：
    - 为了简单，目标虚存区间要求按页对齐，len 可直接按页向上取整，不考虑分配失败时的页回收。
- 可能的错误：
    - start 没有按页大小对齐
    - prot & !0x7 != 0 (prot 其余位必须为0)
    - prot & 0x7 = 0 (这样的内存无意义)
    - [start, start + len) 中存在已经被映射的页
    - 物理内存不足

munmap 定义如下：

.. code-block:: rust

    fn sys_munmap(start: usize, len: usize) -> isize

- syscall ID：215
- 取消到 [start, start + len) 虚存的映射
- 参数和返回值请参考 mmap
- 说明：
    - 为了简单，参数错误时不考虑内存的恢复和回收。
- 可能的错误：
    - [start, start + len) 中存在未被映射的虚存。


TIPS：注意 prot 参数的语义，它与内核定义的 MapPermission 有明显不同！

实验要求
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- 实现分支：ch4-lab
- 实验目录要求不变
- 通过所有测例

  在 os 目录下 ``make run TEST=1`` 测试 sys_get_time， ``make run TEST=2`` 测试 map 和 unmap。

challenge: 支持多核。

问答作业
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

无

实验练习的提交报告要求
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* 简单总结本次实验与上个实验相比你增加的东西。（控制在5行以内，不要贴代码）
* 完成问答问题。
* (optional) 你对本次实验设计及难度的看法。
   
