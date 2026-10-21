pragma solidity 0.6.8;

contract NFTXVaultUpgradeable is PausableUpgradeable, ERC20BurnableUpgradeable, ERC20FlashMintUpgradeable, ReentrancyGuardUpgradeable, ERC721HolderUpgradeable, ERC1155HolderUpgradeable {
    using SafeMathUpgradeable for uint256;
    using EnumerableSetUpgradeable for EnumerableSetUpgradeable.UintSet;

    uint256 constant base = 10**18;

    uint256 public vaultId;
    address public manager;
    address public assetAddress;
    INFTXVaultFactory public vaultFactory;
    INFTXEligibility public eligibilityStorage;

    uint256 randNonce;
    uint256 public mintFee;
    uint256 public redeemFee;
    uint256 public directRedeemFee;
    uint256 public swapFee;

    bool public is1155;
    bool public allowAllItems;
    bool public enableMint;
    bool public enableRedeem;
    bool public enableDirectRedeem;
    bool public enableSwap;
    bool[20] _bool_gap;

    string public description;

    EnumerableSetUpgradeable.UintSet holdings;
    mapping(uint256 => uint256) quantity1155;

    function getRandomTokenIdFromFund() internal virtual returns (uint256) {
        uint256 randomIndex = getPseudoRand(holdings.length());
        return holdings.at(randomIndex);
    }

    function getPseudoRand(uint256 modulus) internal virtual returns (uint256) {
        randNonce += 1;
        return uint256(keccak256(abi.encodePacked(blockhash(block.number - 1), randNonce))) % modulus;
    }

    uint256[25] ___gap;
}
