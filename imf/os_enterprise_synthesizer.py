"""
Operating Systems & Enterprise Systems Synthesizer (IMF).
Covers:
1. Windows Win32 Internals & NT Kernel (PE/COFF, IOCP, Handles, Security Descriptors).
2. Windows Server, Active Directory & PowerShell (Kerberos, GPO, LDAP, DSC, SMB).
3. macOS Darwin, Mach Kernel & XPC (Mach ports, libdispatch GCD, sandboxing, entitlements).
4. Apple Silicon ARM64 & Mach-O (Pointer Authentication PAC, universal binaries, Metal compute).
"""

from typing import List, Tuple
import random

class OSEnterpriseSynthesizer:
    def __init__(self, seed: int = 101):
        self.rng = random.Random(seed)

    def generate_win32_internals(self) -> str:
        samples = [
            ("#include <windows.h>\n#include <stdio.h>\n\n"
             "// Asynchronous I/O via I/O Completion Ports (IOCP)\n"
             "HANDLE CreateWorkerThreadPool(DWORD numThreads) {\n"
             "    HANDLE hIOCP = CreateIoCompletionPort(INVALID_HANDLE_VALUE, NULL, 0, numThreads);\n"
             "    if (hIOCP == NULL) {\n"
             "        DWORD err = GetLastError();\n"
             "        fprintf(stderr, \"CreateIoCompletionPort failed: 0x%08X\\n\", err);\n"
             "        return NULL;\n"
             "    }\n"
             "    return hIOCP;\n"
             "}\n\n"
             "BOOL BindSocketToIOCP(HANDLE hIOCP, SOCKET s, ULONG_PTR completionKey) {\n"
             "    HANDLE hResult = CreateIoCompletionPort((HANDLE)s, hIOCP, completionKey, 0);\n"
             "    return (hResult != NULL);\n"
             "}"),
            
            ("#include <windows.h>\n#include <sddl.h>\n\n"
             "// Security Descriptor & Discretionary Access Control List (DACL)\n"
             "BOOL SetExplicitDACL(HANDLE hObject, SE_OBJECT_TYPE objType) {\n"
             "    PACL pOldDACL = NULL, pNewDACL = NULL;\n"
             "    PSECURITY_DESCRIPTOR pSD = NULL;\n"
             "    DWORD dwRes = GetSecurityInfo(hObject, objType, DACL_SECURITY_INFORMATION, NULL, NULL, &pOldDACL, NULL, &pSD);\n"
             "    if (dwRes != ERROR_SUCCESS) return FALSE;\n"
             "    // Restrict access to Local System and Domain Admins\n"
             "    EXPLICIT_ACCESS_W ea;\n"
             "    ZeroMemory(&ea, sizeof(EXPLICIT_ACCESS_W));\n"
             "    ea.grfAccessPermissions = GENERIC_READ | GENERIC_WRITE;\n"
             "    ea.grfAccessMode = SET_ACCESS;\n"
             "    ea.grfInheritance = NO_INHERITANCE;\n"
             "    LocalFree(pSD);\n"
             "    return TRUE;\n"
             "}")
        ]
        return self.rng.choice(samples)

    def generate_windows_server_ad(self) -> str:
        samples = [
            ("# PowerShell Enterprise Active Directory & Kerberos Ticket Triage\n"
             "$TargetOU = \"OU=ProductionServers,DC=corp,DC=internal\"\n"
             "$StaleAccounts = Get-ADComputer -Filter * -SearchBase $TargetOU -Properties LastLogonDate, ServicePrincipalName |\n"
             "    Where-Object { $_.LastLogonDate -lt (Get-Date).AddDays(-90) }\n\n"
             "foreach ($Comp in $StaleAccounts) {\n"
             "    Write-Output \"Auditing SPNs for: $($Comp.Name)\"\n"
             "    $Comp.ServicePrincipalName | ForEach-Object {\n"
             "        if ($_ -match \"^MSSQLSvc|HTTP\") {\n"
             "            Write-Warning \"High-privilege SPN detected on dormant host: $_\"\n"
             "        }\n"
             "    }\n"
             "}\n\n"
             "# Kerberos ticket cache purge & validation\n"
             "klist purge\n"
             "klist get krbtgt/CORP.INTERNAL"),
            
            ("# Active Directory Group Policy (GPO) Enforcement via CIM/WMI\n"
             "Import-Module GroupPolicy\n"
             "$GPO = Get-GPO -Name \"Secured_Hardened_Baseline\"\n"
             "$ReportPath = \"C:\\Windows\\Temp\\GPO_Compliance_Report.xml\"\n"
             "Get-GPOReport -Guid $GPO.Id -ReportType Xml -Path $ReportPath\n\n"
             "# Enforce SMBv3 Encryption & Disable SMBv1 across fleet\n"
             "Set-SmbServerConfiguration -EncryptData $true -EnableSMB1Protocol $false -Force")
        ]
        return self.rng.choice(samples)

    def generate_macos_mach_xpc(self) -> str:
        samples = [
            ("#import <Foundation/Foundation.h>\n#import <xpc/xpc.h>\n\n"
             "// macOS Darwin XPC Inter-Process Communication Service\n"
             "void init_xpc_server(const char *mach_service_name) {\n"
             "    xpc_connection_t listener = xpc_connection_create_mach_service(\n"
             "        mach_service_name,\n"
             "        dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_HIGH, 0),\n"
             "        XPC_CONNECTION_MACH_SERVICE_LISTENER\n"
             "    );\n"
             "    xpc_connection_set_event_handler(listener, ^(xpc_object_t peer) {\n"
             "        if (xpc_get_type(peer) == XPC_TYPE_CONNECTION) {\n"
             "            xpc_connection_set_event_handler(peer, ^(xpc_object_t event) {\n"
             "                if (xpc_get_type(event) == XPC_TYPE_DICTIONARY) {\n"
             "                    int64_t op = xpc_dictionary_get_int64(event, \"operation_id\");\n"
             "                    xpc_object_t reply = xpc_dictionary_create_reply(event);\n"
             "                    xpc_dictionary_set_bool(reply, \"status_ack\", true);\n"
             "                    xpc_connection_send_message(peer, reply);\n"
             "                }\n"
             "            });\n"
             "            xpc_connection_resume(peer);\n"
             "        }\n"
             "    });\n"
             "    xpc_connection_resume(listener);\n"
             "}"),
            
            ("#include <mach/mach.h>\n#include <mach/task.h>\n#include <stdio.h>\n\n"
             "// Mach Port Kernel Right Allocation & Task Virtual Memory\n"
             "kern_return_t allocate_guarded_mach_memory(task_t target_task, vm_size_t size, vm_address_t *addr) {\n"
             "    kern_return_t kr = vm_allocate(target_task, addr, size, VM_FLAGS_ANYWHERE);\n"
             "    if (kr != KERN_SUCCESS) {\n"
             "        mach_error(\"vm_allocate failed:\", kr);\n"
             "        return kr;\n"
             "    }\n"
             "    // Protect memory to READ|EXECUTE (W^X compliance)\n"
             "    kr = vm_protect(target_task, *addr, size, FALSE, VM_PROT_READ | VM_PROT_EXECUTE);\n"
             "    return kr;\n"
             "}")
        ]
        return self.rng.choice(samples)

    def generate_corpus(self, num_samples: int = 100) -> List[Tuple[str, str]]:
        corpus = []
        generators = [
            (self.generate_win32_internals, "os_windows_win32_internals"),
            (self.generate_windows_server_ad, "os_windows_server_ad_powershell"),
            (self.generate_macos_mach_xpc, "os_macos_darwin_mach_xpc")
        ]
        for _ in range(num_samples):
            fn, tag = self.rng.choice(generators)
            corpus.append((fn(), tag))
        return corpus

if __name__ == "__main__":
    syn = OSEnterpriseSynthesizer()
    c = syn.generate_corpus(3)
    for text, tag in c:
        print(f"=== {tag} ===")
        print(text[:200] + "...\n")
