pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;

struct TokenLoanParams {
    uint128 valuation;
    uint64 duration;
    uint16 annualInterestBPS;
    uint16 ltvBPS;
    INFTOracle oracle;
}

struct SignatureParams {
    uint256 deadline;
    uint8 v;
    bytes32 r;
    bytes32 s;
}

interface ILendingClub {
    function willLend(uint256 tokenId, TokenLoanParams memory params) external view returns (bool);

    function lendingConditions(address nftPair, uint256 tokenId) external view returns (TokenLoanParams memory);
}

interface INFTPair {
    function collateral() external view returns (IERC721);

    function asset() external view returns (IERC20);

    function masterContract() external view returns (address);

    function bentoBox() external view returns (IBentoBoxV1);

    function removeCollateral(uint256 tokenId, address to) external;
}

contract NFTPairWithOracle is BoringOwnable, Domain, IMasterContract {
    using BoringMath for uint256;
    using BoringMath128 for uint128;
    using RebaseLibrary for Rebase;
    using BoringERC20 for IERC20;

    event LogLend(address indexed lender, uint256 indexed tokenId);

    IBentoBoxV1 public immutable bentoBox;
    NFTPairWithOracle public immutable masterContract;

    address public feeTo;

    IERC721 public collateral;
    IERC20 public asset;

    uint256 public feesEarnedShare;

    mapping(uint256 => TokenLoanParams) public tokenLoanParams;

    uint8 private constant LOAN_INITIAL = 0;
    uint8 private constant LOAN_REQUESTED = 1;
    uint8 private constant LOAN_OUTSTANDING = 2;
    struct TokenLoan {
        address borrower;
        address lender;
        uint64 startTime;
        uint8 status;
    }
    mapping(uint256 => TokenLoan) public tokenLoan;

    uint256 private constant PROTOCOL_FEE_BPS = 1000;
    uint256 private constant OPEN_FEE_BPS = 100;
    uint256 private constant BPS = 10_000;
    uint256 private constant YEAR_BPS = 3600 * 24 * 365 * 10_000;

    uint8 private constant COMPOUND_INTEREST_TERMS = 6;

    mapping(address => uint256) public nonces;

    function _lend(address lender, uint256 tokenId, TokenLoanParams memory accepted, bool skim) internal {
        TokenLoan memory loan = tokenLoan[tokenId];
        require(loan.status == LOAN_REQUESTED, "NFTPair: not available");
        TokenLoanParams memory params = tokenLoanParams[tokenId];

        require(params.valuation == accepted.valuation && params.duration <= accepted.duration && params.annualInterestBPS >= accepted.annualInterestBPS && params.ltvBPS >= accepted.ltvBPS, "NFTPair: bad params");

        if (params.oracle != INFTOracle(0)) {
            (, uint256 rate) = params.oracle.get(address(this), tokenId);
            require(rate.mul(uint256(params.ltvBPS)) / BPS >= params.valuation, "Oracle: price too low.");
        }

        uint256 totalShare = bentoBox.toShare(asset, params.valuation, false);
        uint256 openFeeShare = (totalShare * OPEN_FEE_BPS) / BPS;
        uint256 protocolFeeShare = (openFeeShare * PROTOCOL_FEE_BPS) / BPS;

        if (skim) {
            require(bentoBox.balanceOf(asset, address(this)) >= (totalShare - openFeeShare + protocolFeeShare + feesEarnedShare), "NFTPair: skim too much");
        } else {
            bentoBox.transfer(asset, lender, address(this), totalShare - openFeeShare + protocolFeeShare);
        }
        uint256 borrowerShare = totalShare - openFeeShare;
        bentoBox.transfer(asset, address(this), loan.borrower, borrowerShare);
        feesEarnedShare += protocolFeeShare;

        loan.lender = lender;
        loan.status = LOAN_OUTSTANDING;
        loan.startTime = uint64(block.timestamp);
        tokenLoan[tokenId] = loan;

        emit LogLend(lender, tokenId);
    }

    bytes32 private constant LEND_SIGNATURE_HASH = 0x4bfd5d24664945f4bb81f6061bd624907d74ba338190bdd6aa37f65838a8a533;

    bytes32 private constant BORROW_SIGNATURE_HASH = 0xfc58c7a8ea6a96e25d218e36759058a704bbf0bebb53a109a44ca82f025cb769;

    uint8 internal constant ACTION_REPAY = 2;
    uint8 internal constant ACTION_REMOVE_COLLATERAL = 4;

    uint8 internal constant ACTION_REQUEST_LOAN = 12;
    uint8 internal constant ACTION_LEND = 13;

    uint8 internal constant ACTION_BENTO_DEPOSIT = 20;
    uint8 internal constant ACTION_BENTO_WITHDRAW = 21;
    uint8 internal constant ACTION_BENTO_TRANSFER = 22;
    uint8 internal constant ACTION_BENTO_TRANSFER_MULTIPLE = 23;
    uint8 internal constant ACTION_BENTO_SETAPPROVAL = 24;

    uint8 internal constant ACTION_CALL = 30;

    uint8 internal constant ACTION_REQUEST_AND_BORROW = 40;
    uint8 internal constant ACTION_TAKE_COLLATERAL_AND_LEND = 41;

    int256 internal constant USE_VALUE1 = -1;
    int256 internal constant USE_VALUE2 = -2;

}
