
Bug #006: Error de KVM y NEM en VirtualBox
Severidad: Crítica
Módulo: Entorno / VirtualBox
Entorno: Windows 11, VirtualBox 7.x, CPU AMD Ryzen
Fecha: 2026-09

Descripción
La VM se apaga inmediatamente después de arrancar. Logs muestran errores de KVM y NEM.

Pasos para reproducir
Iniciar VM de Whonix en VirtualBox.

Observar la consola de logs.

Resultado esperado
VM arranca y permanece encendida.

Resultado obtenido
text
GIM: KVM: Resetting MSRs
NEM: Destroying partition 00000279363fdf10 with its 3 VCpus...
vmmR3LogFlusher: Terminating (VERR_OBJECT_DESTROYED)
Changing the VM state from 'DESTROYING' to 'TERMINATED'
Causa raíz
VirtualBox intenta usar KVM (Kernel-based Virtual Machine, propio de Linux) en lugar de su motor nativo NEM (Native Execution Mode) en Windows. Esto ocurre cuando Hyper-V está parcialmente activo o hay conflicto con el hipervisor de Windows.

Solución aplicada
Desactivar Hyper-V completamente (ver Bug #004).

Forzar a VirtualBox a usar NEM:

cmd
VBoxManage modifyvm "Whonix-Gateway" --nested-hw-virt on
VBoxManage modifyvm "Whonix-Gateway" --paravirtprovider kvm
En configuración de la VM:

Sistema → Procesador → Habilitar PAE/NX: ✓

Aceleración → Interfaz de Paravirtualización: KVM o Default.

Verificación
VM arranca y permanece estable.

No más errores en la consola de logs.

Lección aprendida
En CPUs AMD con Windows 11, VirtualBox necesita configuración explícita de paravirtualización. No basta con desactivar Hyper-V. Documentar el comando VBoxManage modifyvm es crítico para futuras instalaciones.
