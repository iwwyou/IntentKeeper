pragma solidity 0.8.9;

library AddressProviderHelpers {
    function getTreasury(IAddressProvider provider) internal view returns (address) {
        return provider.getAddress(AddressProviderKeys._TREASURY_KEY);
    }

    function getGasBank(IAddressProvider provider) internal view returns (IGasBank) {
        return IGasBank(provider.getAddress(AddressProviderKeys._GAS_BANK_KEY));
    }

    function getVaultReserve(IAddressProvider provider) internal view returns (IVaultReserve) {
        return IVaultReserve(provider.getAddress(AddressProviderKeys._VAULT_RESERVE_KEY));
    }

    function getSwapperRegistry(IAddressProvider provider) internal view returns (address) {
        return provider.getAddress(AddressProviderKeys._SWAPPER_REGISTRY_KEY);
    }

    function getOracleProvider(IAddressProvider provider) internal view returns (IOracleProvider) {
        return IOracleProvider(provider.getAddress(AddressProviderKeys._ORACLE_PROVIDER_KEY));
    }

    function getBKDLocker(IAddressProvider provider) internal view returns (address) {
        return provider.getAddress(AddressProviderKeys._BKD_LOCKER_KEY);
    }

    function getRoleManager(IAddressProvider provider) internal view returns (IRoleManager) {
        return IRoleManager(provider.getAddress(AddressProviderKeys._ROLE_MANAGER_KEY));
    }

    function getController(IAddressProvider provider) internal view returns (IController) {
        return IController(provider.getAddress(AddressProviderKeys._CONTROLLER_KEY));
    }
}
