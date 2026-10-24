
extern void work(void); extern volatile int glob;
void __attribute__((interrupt(""))) irq_empty(void) { }
void __attribute__((interrupt(""))) irq(void) { glob++; work(); }
void __attribute__((naked)) naked(void) { __asm__ volatile("rts"); }
int __attribute__((section(".mycode"))) insection(int x) { return x+1; }
int __attribute__((section(".mydata"))) datum=7;
int readglobal(void) { return glob; } int *address(void) { return &datum; }
const char *string(void) { return "pi32v2"; }
unsigned constant(void) { return 0x12345678; }
float fc(void) { return 1.25f; } double dc(void) { return 1.25; }
extern const int table[16]; int lookup(unsigned i) { return table[i&15]; }
