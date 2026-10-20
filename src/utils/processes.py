import ctypes
import ctypes.wintypes as wintypes


QUERY_LIMITED_INFORMATION = 0x1000
VM_READ = 0x0010
TARGETS = ("riot client.exe", "riotclientservices.exe", "riotclientux.exe")


def _read_memory(kernel, handle, address, size):
    """Lê bytes de outro processo, quando há permissão de acesso."""
    buffer = ctypes.create_string_buffer(size)
    received = ctypes.c_size_t()
    success = kernel.ReadProcessMemory(
        handle, ctypes.c_void_p(address), buffer, size, ctypes.byref(received)
    )
    if not success:
        return None
    return buffer.raw[:received.value]


def _read_command_line(kernel, handle, peb_address):
    """Segue os ponteiros de parâmetros e da linha de comando no PEB de 64 bits."""
    parameters_raw = _read_memory(kernel, handle, peb_address + 0x20, 8)
    if not parameters_raw:
        return None

    parameters_address = int.from_bytes(parameters_raw, "little")
    unicode_string = _read_memory(kernel, handle, parameters_address + 0x70, 16)
    if not unicode_string:
        return None

    length = int.from_bytes(unicode_string[:2], "little")
    text_address = int.from_bytes(unicode_string[8:16], "little")
    if not length:
        return ""

    text = _read_memory(kernel, handle, text_address, length)
    if text is None:
        return None
    return text.decode("utf-16-le", errors="replace")


def _image_name(kernel, handle):
    """Obtém o caminho do executável associado a um processo."""
    size = wintypes.DWORD(1024)
    buffer = ctypes.create_unicode_buffer(512)
    if kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
        return buffer.value
    return ""


def find_riot_cmdlines():
    """Devolve as linhas de comando dos processos Riot que podem ser lidos."""
    if ctypes.sizeof(ctypes.c_void_p) != 8:
        raise RuntimeError("A leitura dos processos exige Python de 64 bits")

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    process_api = ctypes.WinDLL("psapi")
    native_api = ctypes.WinDLL("ntdll")

    # Sem estas assinaturas, ctypes pode truncar handles de 64 bits.
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel.ReadProcessMemory.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t),
    ]
    kernel.QueryFullProcessImageNameW.argtypes = [
        ctypes.c_void_p, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
    ]
    native_api.NtQueryInformationProcess.argtypes = [
        ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p,
        wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
    ]

    process_ids = (wintypes.DWORD * 65536)()
    received = wintypes.DWORD()
    process_api.EnumProcesses(
        ctypes.byref(process_ids), ctypes.sizeof(process_ids), ctypes.byref(received)
    )

    command_lines = {}
    count = received.value // ctypes.sizeof(wintypes.DWORD)
    for process_id in process_ids[:count]:
        if not process_id:
            continue

        handle = kernel.OpenProcess(QUERY_LIMITED_INFORMATION, False, process_id)
        if not handle:
            continue
        try:
            name = _image_name(kernel, handle).lower()
        finally:
            kernel.CloseHandle(handle)
        if not any(name.endswith("\\" + target) for target in TARGETS):
            continue

        handle = kernel.OpenProcess(QUERY_LIMITED_INFORMATION | VM_READ, False, process_id)
        if not handle:
            continue
        try:
            # PROCESS_BASIC_INFORMATION tem seis ponteiros em processos de 64 bits.
            info = ctypes.create_string_buffer(ctypes.sizeof(ctypes.c_void_p) * 6)
            result_length = wintypes.DWORD()
            status = native_api.NtQueryInformationProcess(
                handle, 0, ctypes.byref(info), ctypes.sizeof(info), ctypes.byref(result_length)
            )
            if status != 0:
                continue
            peb_address = ctypes.c_void_p.from_buffer(info, ctypes.sizeof(ctypes.c_void_p)).value
            if peb_address:
                command_line = _read_command_line(kernel, handle, peb_address)
                if command_line:
                    command_lines[process_id] = command_line
        finally:
            kernel.CloseHandle(handle)
    return command_lines
