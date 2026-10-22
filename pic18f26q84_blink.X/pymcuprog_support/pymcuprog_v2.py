"""Run Microchip pymcuprog through the Snap CMSIS-DAP v2 adapter."""

from cmsisdap_v2_transport import bulk_transport
import pymcuprog.backend


# pymcuprog imports the transport factory into its backend module.  Replace
# that factory only; all programming and device-pack logic remains upstream.
pymcuprog.backend.hid_transport = bulk_transport

from pymcuprog.pymcuprog import main  # noqa: E402  (patch before CLI import)


if __name__ == "__main__":
    main()
