练习参考答案
=====================================================

.. toctree::
      :hidden:
      :maxdepth: 4

课后练习
-------------------------------

编程题
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. `*` 分别编写基于UNIX System V IPC的管道、共享内存、信号量和消息队列的Linux应用程序，实现进程间的数据交换。

    管道

    .. code-block:: c
        :linenos:

        #include <unistd.h>
        #include <stdio.h>
        #include <stdlib.h>
        #include <string.h>
        
        int main(void) {
          int pipefd[2];
          // pipe syscall creates a pipe with two ends
          // pipefd[0] is the read end
          // pipefd[1] is the write end
          // ref: https://man7.org/linux/man-pages/man2/pipe.2.html
          if (pipe(pipefd) == -1) {
            perror("failed to create pipe");
            exit(EXIT_FAILURE);
          }
        
          int pid = fork();
          if (pid == -1) {
            perror("failed to fork");
            exit(EXIT_FAILURE);
          }
        
          if (pid == 0) {
            // child process reads from the pipe
            close(pipefd[1]); // close the write end
            // read a byte at a time
            char buf;
            while (read(pipefd[0], &buf, 1) > 0) {
              printf("%s", &buf);
            }
            close(pipefd[0]); // close the read end
          } else {
            // parent process writes to the pipe
            close(pipefd[0]); // close the read end
            // parent writes
            char* msg = "hello from pipe\n";
            write(pipefd[1], msg, strlen(msg)); // omitting error handling
            close(pipefd[1]); // close the write end
          }
        
          return EXIT_SUCCESS;
        }

    共享内存

    .. code-block:: c
        :linenos:

        #include <unistd.h>
        #include <stdio.h>
        #include <stdlib.h>
        #include <string.h>
        #include <sys/shm.h>
        
        int main(void) {
          // create a new anonymous shared memory segment of page size, with a permission of 0600
          // ref: https://man7.org/linux/man-pages/man2/shmget.2.html
          int shmid = shmget(IPC_PRIVATE, sysconf(_SC_PAGESIZE), IPC_CREAT | 0600);
          if (shmid == -1) {
            perror("failed to create shared memory");
            exit(EXIT_FAILURE);
          }
        
          int pid = fork();
          if (pid == -1) {
            perror("failed to fork");
            exit(EXIT_FAILURE);
          }
        
          if (pid == 0) {
            // attach the shared memory into child process's address space
            char* shm = shmat(shmid, NULL, 0);
            while (!shm[0]) {
              // wait until the parent signals that the data is ready
              // WARNING: this is not the correct way to synchronize processes
              // on SMP systems due to memory orders, but this implementation
              // is chosen here specifically for ease of understanding
            }
            printf("%s", shm + 1);
          } else {
            // attach the shared memory into parent process's address space
            char* shm = shmat(shmid, NULL, 0);
            // copy message into shared memory
            strcpy(shm + 1, "hello from shared memory\n");
            // signal that the data is ready
            shm[0] = 1;
          }
        
          return EXIT_SUCCESS;
        }

    信号量

    .. code-block:: c
        :linenos:

        #include <unistd.h>
        #include <stdio.h>
        #include <stdlib.h>
        #include <string.h>
        #include <sys/sem.h>
        
        int main(void) {
          // create a new anonymous semaphore set, with permission 0600
          // ref: https://man7.org/linux/man-pages/man2/semget.2.html
          int semid = semget(IPC_PRIVATE, 1, IPC_CREAT | 0600);
          if (semid == -1) {
            perror("failed to create semaphore");
            exit(EXIT_FAILURE);
          }
        
          struct sembuf sops[1];
          sops[0].sem_num = 0; // operate on semaphore 0
          sops[0].sem_op  = 1; // increase the semaphore's value by 1
          sops[0].sem_flg = 0;
          if (semop(semid, sops, 1) == -1) {
            perror("failed to increase semaphore");
            exit(EXIT_FAILURE);
          }
        
          int pid = fork();
          if (pid == -1) {
            perror("failed to fork");
            exit(EXIT_FAILURE);
          }
        
          if (pid == 0) {
            printf("hello from child, waiting for parent to release semaphore\n");
            struct sembuf sops[1];
            sops[0].sem_num = 0; // operate on semaphore 0
            sops[0].sem_op  = 0; // wait for the semaphore to become 0
            sops[0].sem_flg = 0;
            if (semop(semid, sops, 1) == -1) {
              perror("failed to wait on semaphore");
              exit(EXIT_FAILURE);
            }
            printf("hello from semaphore\n");
          } else {
            printf("hello from parent, waiting three seconds before release semaphore\n");
            // sleep for three second
            sleep(3);
            struct sembuf sops[1];
            sops[0].sem_num = 0; // operate on semaphore 0
            sops[0].sem_op  = -1; // decrease the semaphore's value by 1
            sops[0].sem_flg = 0;
            if (semop(semid, sops, 1) == -1) {
              perror("failed to decrease semaphore");
              exit(EXIT_FAILURE);
            }
          }
        
          return EXIT_SUCCESS;
        }

    消息队列

    .. code-block:: c
        :linenos:

        #include <unistd.h>
        #include <stdio.h>
        #include <stdlib.h>
        #include <string.h>
        #include <sys/msg.h>
        
        struct msgbuf {
          long mtype;
          char mtext[1];
        };
        
        int main(void) {
          // create a new anonymous message queue, with a permission of 0600
          // ref: https://man7.org/linux/man-pages/man2/msgget.2.html
          int msgid = msgget(IPC_PRIVATE, IPC_CREAT | 0600);
          if (msgid == -1) {
            perror("failed to create message queue");
            exit(EXIT_FAILURE);
          }
        
          int pid = fork();
          if (pid == -1) {
            perror("failed to fork");
            exit(EXIT_FAILURE);
          }
        
          if (pid == 0) {
            // child process receives message
            struct msgbuf buf;
            while (msgrcv(msgid, &buf, sizeof(buf.mtext), 1, 0) != -1) {
              printf("%c", buf.mtext[0]);
            }
          } else {
            // parent process sends message
            char* msg = "hello from message queue\n";
            struct msgbuf buf;
            buf.mtype = 1;
            for (int i = 0; i < strlen(msg); i ++) {
              buf.mtext[0] = msg[i];
              msgsnd(msgid, &buf, sizeof(buf.mtext), 0);
            }
            struct msqid_ds info;
            while (msgctl(msgid, IPC_STAT, &info), info.msg_qnum > 0) {
              // wait for the message queue to be fully consumed
            }
            // close message queue
            msgctl(msgid, IPC_RMID, NULL);
          }
        
          return EXIT_SUCCESS;
        }

2. `**` 分别编写基于UNIX的signal机制的Linux应用程序，实现进程间异步通知。

    .. code-block:: c
        :linenos:

        #include <unistd.h>
        #include <stdio.h>
        #include <stdlib.h>
        #include <signal.h>
        
        static void sighandler(int sig) {
          printf("received signal %d, exiting\n", sig);
          exit(EXIT_SUCCESS);
        }
        
        int main(void) {
          struct sigaction sa;
          sa.sa_handler = sighandler;
          sa.sa_flags = 0;
          sigemptyset(&sa.sa_mask);
          // register function sighandler as signal handler for SIGUSR1
          if (sigaction(SIGUSR1, &sa, NULL) != 0) {
            perror("failed to register signal handler");
            exit(EXIT_FAILURE);
          }
        
          int pid = fork();
          if (pid == -1) {
            perror("failed to fork");
            exit(EXIT_FAILURE);
          }
        
          if (pid == 0) {
            while (1) {
              // loop and wait for signal
            }
          } else {
            // send SIGUSR1 to child process
            kill(pid, SIGUSR1);
          }
        
          return EXIT_SUCCESS;
        }

3. `**` 参考rCore Tutorial 中的shell应用程序，在Linux环境下，编写一个简单的shell应用程序，通过管道相关的系统调用，能够支持管道功能。

    .. code-block:: c
        :linenos:

        #include <stdio.h>
        #include <stdlib.h>
        #include <string.h>
        #include <sys/wait.h>
        #include <unistd.h>
        
        int parse(char* line, char** argv) {
          size_t len;
          // read a line from stdin
          if (getline(&line, &len, stdin) == -1)
            return -1;
          // remove trailing newline
          line[strlen(line) - 1] = '\0';
          // split line into tokens
          int i = 0;
          char* token = strtok(line, " ");
          while (token != NULL) {
            argv[i] = token;
            token = strtok(NULL, " ");
            i++;
          }
          return 0;
        }
        
        int concat(char** argv1, char** argv2) {
            // create pipe
            int pipefd[2];
            if (pipe(pipefd) == -1)
              return -1;
        
            // run the first command
            int pid1 = fork();
            if (pid1 == -1)
              return -1;
            if (pid1 == 0) {
              dup2(pipefd[1], STDOUT_FILENO);
              close(pipefd[0]);
              close(pipefd[1]);
              execvp(argv1[0], argv1);
            }
        
            // run the second command
            int pid2 = fork();
            if (pid2 == -1)
              return -1;
            if (pid2 == 0) {
              dup2(pipefd[0], STDIN_FILENO);
              close(pipefd[0]);
              close(pipefd[1]);
              execvp(argv2[0], argv2);
            }
        
            // wait for them to exit
            close(pipefd[0]);
            close(pipefd[1]);
            wait(&pid1);
            wait(&pid2);
            return 0;
        }
        
        int main(void) {
          printf("[command 1]$ ");
          char* line1 = NULL;
          char* argv1[16] = {NULL};
          if (parse(line1, argv1) == -1) {
            exit(EXIT_FAILURE);
          }
          printf("[command 2]$ ");
          char* line2 = NULL;
          char* argv2[16] = {NULL};
          if (parse(line2, argv2) == -1) {
            exit(EXIT_FAILURE);
          }
          concat(argv1, argv2);
          free(line1);
          free(line2);
        }

4. `**` 扩展内核，实现共享内存机制。

    略

5. `***` 扩展内核，实现signal机制。

    略，设计思路可参见问答题2。

问答题
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. `*` 直接通信和间接通信的本质区别是什么？分别举一个例子。

    本质区别是消息是否经过内核，如共享内存就是直接通信，消息队列则是间接通信。

2. `**` 试说明基于UNIX的signal机制，如果在本章内核中实现，请描述其大致设计思路和运行过程。

    首先需要添加两个syscall，其一是注册signal handler，其二是发送signal。其次是添加对应的内核数据结构，对于每个进程需要维护两个表，其一是signal到handler地址的对应，其二是尚未处理的signal。当进程注册signal handler时，将所注册的处理函数的地址填入表一。当进程发送signal时，找到目标进程，将signal写入表二的队列之中。随后修改从内核态返回用户态的入口点的代码，检查是否有待处理的signal。若有，检查是否有对应的signal handler并跳转到该地址，如无则执行默认操作，如杀死进程。需要注意的是，此时需要记住原本的跳转地址，当进程从signal handler返回时将其还原。

3. `**` 比较在Linux中的无名管道（普通管道）与有名管道（FIFO）的异同。

    同：两者都是进程间信息单向传递的通路，可以在进程之间传递一个字节流。异：普通管道不存在文件系统上对应的文件，而是仅由读写两端两个fd表示，而FIFO则是由文件系统上的一个特殊文件表示，进程打开该文件后获得对应的fd。

4. `**` 请描述Linux中的无名管道机制的特征和适用场景。

    无名管道用于创建在进程间传递的一个字节流，适合用于流式传递大量数据，但是进程需要自己处理消息间的分割。

5. `**` 请描述Linux中的消息队列机制的特征和适用场景。

    消息队列用于在进程之间发送一个由type和data两部分组成的短消息，接收消息的进程可以通过type过滤自己感兴趣的消息，适用于大量进程之间传递短小而多种类的消息。

6. `**` 请描述Linux中的共享内存机制的特征和适用场景。

    共享内存用于创建一个多个进程可以同时访问的内存区域，故而消息的传递无需经过内核的处理，适用在需要较高性能的场景，但是进程之间需要额外的同步机制处理读写的顺序与时机。

7. `**` 请描述Linux的bash shell中执行与一个程序时，用户敲击 `Ctrl+C` 后，会产生什么信号（signal），导致什么情况出现。

    会产生SIGINT，如果该程序没有捕获该信号，它将会被杀死，若捕获了，通常会在处理完或是取消当前正在进行的操作后主动退出。

8. `**` 请描述Linux的bash shell中执行与一个程序时，用户敲击 `Ctrl+Zombie` 后，会产生什么信号（signal），导致什么情况出现。

    会产生SIGTSTP，该进程将会暂停运行，将控制权重新转回shell。

9. `**` 请描述Linux的bash shell中执行 `kill -9 2022` 这个命令的含义是什么？导致什么情况出现。

    向pid为2022的进程发送SIGKILL，该信号无法被捕获，该进程将会被强制杀死。

10. `**` 请指出一种跨计算机的主机间的进程间通信机制。

    一个在过去较为常用的例子是Sun RPC。
