<?php

class StoreModuleOrder {

	const STATE_PENDING = 'pending';
	const STATE_PAID = 'paid';
	const STATE_COMPLETE = 'complete';
	const STATE_FAILED = 'failed';
	const STATE_REFUNDED = 'refunded';
	const STATE_CANCELLED = 'cancelled';

	/** @return string[] */
	public static function getStates() {
		return array(
			self::STATE_PENDING,
			self::STATE_PAID,
			self::STATE_COMPLETE,
			self::STATE_FAILED,
			self::STATE_REFUNDED,
			self::STATE_CANCELLED,
		);
	}

	const FILTER_ID = 'id';
	const FILTER_TRANSACTION_ID = 'transactionId';
	const FILTER_EXT_TRANSACTION_ID = 'extTransactionId';
	const FILTER_STATE = 'state';
	const FILTER_DATE_TIME_LTE = 'dateTimeLte';
	const FILTER_DATE_TIME_GTE = 'dateTimeGte';
	const FILTER_HASH = 'hash';

	private $id;
	private $transactionId;
	private $extTransactionId;
	private $gatewayId;
	private $lang;
	private $buyer;
	/** @var StoreModuleOrderItem[]|string[] */
	private $items;
	private $price;
	private $type;
	/** @var string|null */
	private $state;
	private $dateTime;
	private $completeDateTime;
	private $cancelDateTime;
	/** @var string */
	private $stateDateTime = '';
	/** @var array|null */
	private $billingForm;
	/** @var StoreBillingInfo|null */
	private $billingInfo;
	/** @var StoreBillingInfo|null */
	private $deliveryInfo;
	/** @var string */
	private $orderComment = '';
	/** @var StoreModuleOrderTax[] */
	private $taxes = [];
	/** @var float */
	private $shippingAmount = 0;
	/** @var string */
	private $shippingDescription = '';
	/** @var float */
	private $discountAmount = 0;
	/** @var StoreCurrency|null */
	private $currency = null;
	/** @var StorePriceOptions|null */
	private $priceOptions = null;
	/** @var array */
	private $customFields = array();
	/** @var string|null */
	private $invoiceDocumentNumber = null;
	/** @var bool */
	private $stockManaged = false;
	/** @var int */
	private $stockAppliedVersion = 0;
	/** @var ?StoreCoupon */
	private $coupon = null;

	/** @var bool */
	private $invoiceON = true;

	/** @var bool */
	private $invoiceResended = false;

	private static $logLockFile = null;

	public static function create($transactionId = null) {
		return new self($transactionId);
	}

	public function __construct($transactionId = null) {
		$this->transactionId = $transactionId;
		$this->dateTime = date('Y-m-d H:i:s');
	}

	private function populate(array $f) {
		$this->id = isset($f['id']) ? $f['id'] : null;
		$this->transactionId = isset($f['transactionId']) ? $f['transactionId'] : (isset($f['tnx_id']) ? $f['tnx_id'] : null);
		$this->extTransactionId = isset($f['extTransactionId']) ? $f['extTransactionId'] : null;
		$this->gatewayId = isset($f['gatewayId']) ? $f['gatewayId'] : (isset($f['gateway_id']) ? $f['gateway_id'] : null);
		$this->lang = isset($f['lang']) ? $f['lang'] : null;
		$this->buyer = isset($f['buyer']) ? new StoreModuleBuyer($f['buyer']) : null;
		$this->price = isset($f['price']) ? $f['price'] : null;
		$this->type = isset($f['type']) ? $f['type'] : null;
		$this->state = isset($f['state']) ? $f['state'] : null;
		$this->dateTime = isset($f['dateTime']) ? $f['dateTime'] : (isset($f['time']) ? $f['time'] : null);
		$this->completeDateTime = isset($f['completeDateTime']) ? $f['completeDateTime'] : null;
		$this->cancelDateTime = isset($f['cancelDateTime']) ? $f['cancelDateTime'] : null;
		$this->stateDateTime = (isset($f['stateDateTime']) && is_string($f['stateDateTime']))
			? $f['stateDateTime']
			: '';
		if (!$this->stateDateTime) {
			// Note: try filling in for older orders
			if ($this->completeDateTime) $this->stateDateTime = $this->completeDateTime;
			else if ($this->cancelDateTime) $this->stateDateTime = $this->cancelDateTime;
			else if ($this->dateTime) $this->stateDateTime = $this->dateTime;
		}
		$this->billingForm = isset($f['billingForm']) ? $f['billingForm'] : null;
		$this->billingInfo = isset($f['billingInfo']) ? StoreBillingInfo::fromJson($f['billingInfo']) : null;
		$this->deliveryInfo = isset($f['deliveryInfo']) ? StoreBillingInfo::fromJson($f['deliveryInfo']) : null;
		$this->orderComment = (isset($f['orderComment']) && is_string($f['orderComment'])) ? $f['orderComment'] : '';
		$totalTaxAmount = (isset($f['taxAmount']) && is_numeric($f['taxAmount'])) ? floatval($f['taxAmount']) : 0;
		$this->taxes = [];
		if (isset($f['taxes']) && is_array($f['taxes'])) {
			foreach ($f['taxes'] as $taxData) {
				$tax = is_array($taxData) ? StoreModuleOrderTax::fromJson((object) $taxData) : null;
				if ($tax) $this->taxes[] = $tax;
			}
		} else if ($totalTaxAmount > 0) {
			$this->taxes[] = new StoreModuleOrderTax(0, $totalTaxAmount);
		}
		$this->shippingAmount = (isset($f['shippingAmount']) && is_numeric($f['shippingAmount'])) ? floatval($f['shippingAmount']) : 0;
		$this->shippingDescription = (isset($f['shippingDescription']) && $f['shippingDescription']) ? $f['shippingDescription'] : '';
		$this->discountAmount = (isset($f['discountAmount']) && is_numeric($f['discountAmount'])) ? floatval($f['discountAmount']) : 0;
		$this->currency = isset($f['currency']) ? StoreCurrency::fromJson($f['currency']) : null;
		$this->priceOptions = isset($f['priceOptions']) ? StorePriceOptions::fromJson($f['priceOptions']) : null;
		$this->customFields = (isset($f['customFields']) && is_array($f['customFields'])) ? $f['customFields'] : array();
		$this->invoiceDocumentNumber = isset($f['invoiceDocumentNumber']) ? $f['invoiceDocumentNumber'] : null;
		$this->stockManaged = (isset($f['stockManaged']) && $f['stockManaged']);
		$this->stockAppliedVersion = (isset($f['stockAppliedVersion']) && is_numeric($f['stockAppliedVersion']))
			? intval($f['stockAppliedVersion'])
			: 0;
		$this->coupon = (isset($f['coupon']) && is_array($f['coupon']))
			? StoreCoupon::fromJson((object) $f['coupon'])
			: null;

		$this->items = array();
		$items = isset($f['items']) ? $f['items'] : (isset($f['order']) ? $f['order'] : null);
		foreach( $items as $item )
			$this->items[] = (is_object($item) || is_array($item)) ? StoreModuleOrderItem::fromJson($this, $item) : $item;
		$this->invoiceON = isset($f['invoiceON']) ? $f['invoiceON'] : true;
		$this->invoiceResended = isset($f['invoiceResended']) ? $f['invoiceResended'] : false;
	}

	function getId() {
		return $this->id;
	}

	function getTransactionId() {
		return $this->transactionId;
	}

	function getExtTransactionId() {
		return $this->extTransactionId;
	}

	function getGatewayId() {
		return $this->gatewayId;
	}

	function getLang() {
		return $this->lang;
	}

	/** @return StoreModuleBuyer */
	function getBuyer() {
		return $this->buyer;
	}

	function getItems() {
		return $this->items;
	}

	function getPrice() {
		return $this->price;
	}

	function getType() {
		return $this->type;
	}

	function getState() {
		return $this->state;
	}

	function getDateTime() {
		return $this->dateTime;
	}

	function getCompleteDateTime() {
		return $this->completeDateTime;
	}

	function getCancelDateTime() {
		return $this->cancelDateTime;
	}

	/** @return string */
	function getStateDateTime() {
		return $this->stateDateTime;
	}

	/** @return bool */
	function getInvoiceON() {
		return $this->invoiceON;
	}

	/** @return bool */
	function getInvoiceResended() {
		return $this->invoiceResended;
	}

	/** @return StoreModuleOrder */
	function setTransactionId($transactionId) {
		$this->transactionId = $transactionId;
		return $this;
	}

	/** @return StoreModuleOrder */
	function setExtTransactionId($extTransactionId) {
		$this->extTransactionId = $extTransactionId;
		return $this;
	}

	/** @return StoreModuleOrder */
	function setGatewayId($gatewayId) {
		$this->gatewayId = $gatewayId;
		return $this;
	}

	/** @return StoreModuleOrder */
	function setLang($lang) {
		$this->lang = $lang;
		return $this;
	}

	/** @return StoreModuleOrder */
	function setBuyer(StoreModuleBuyer $buyer = null) {
		$this->buyer = $buyer;
		return $this;
	}

	/**
	 * @param StoreModuleOrderItem[]|string[] $items
	 * @return StoreModuleOrder
	 */
	function setItems(array $items = array()) {
		$this->items = $items;
		return $this;
	}

	/** @return StoreModuleOrder */
	function setPrice($price) {
		$this->price = $price;
		return $this;
	}

	/** @return StoreModuleOrder */
	function setType($type) {
		$this->type = $type;
		return $this;
	}

	/** @return StoreModuleOrder */
	function setState($state) {
		if ($this->state != $state) {
			$this->stateDateTime = date('Y-m-d H:i:s');
		}
		$this->state = $state;
		return $this;
	}

	/** @return StoreModuleOrder */
	function setDateTime($dateTime) {
		$this->dateTime = $dateTime;
		return $this;
	}

	/** @return StoreModuleOrder */
	function setCompleteDateTime($completeDateTime) {
		$this->completeDateTime = $completeDateTime;
		return $this;
	}

	/** @return StoreModuleOrder */
	function setCancelDateTime($cancelDateTime) {
		$this->cancelDateTime = $cancelDateTime;
		return $this;
	}

	/**
	 * @param string
	 * @return self
	 */
	function setStateDateTime($stateDateTime) {
		$this->stateDateTime = $stateDateTime;
		return $this;
	}

	/**
	 * @param bool
	 * @return self
	 */
	function setInvoiceON($invoiceON) {
		$this->invoiceON = $invoiceON;
		return $this;
	}

	/**
	 * @param bool
	 * @return self
	 */
	function setInvoiceResended($invoiceResended) {
		$this->invoiceResended = $invoiceResended;
		return $this;
	}

	/** @return array|null */
	public function getBillingForm() {
		return $this->billingForm;
	}

	/** @return StoreBillingInfo|null */
	public function getBillingInfo() {
		return $this->billingInfo;
	}

	/** @return StoreBillingInfo|null */
	public function getDeliveryInfo() {
		return $this->deliveryInfo;
	}

	/** @return StoreModuleOrder */
	public function setBillingForm(array $billingForm = null) {
		$this->billingForm = $billingForm;
		return $this;
	}

	/** @return StoreModuleOrder */
	public function setBillingInfo(StoreBillingInfo $billingInfo = null) {
		$this->billingInfo = $billingInfo;
		return $this;
	}

	/** @return StoreModuleOrder */
	public function setDeliveryInfo(StoreBillingInfo $deliveryInfo = null) {
		$this->deliveryInfo = $deliveryInfo;
		return $this;
	}

	/** @return StoreModuleOrderTax[] */
	public function getTaxes() {
		return $this->taxes;
	}

	/** @return float */
	public function getFullTaxAmount() {
		$result = 0;
		foreach ($this->taxes as $tax) $result += $tax->amount;
		return $result;
	}

	/** @return float */
	public function getShippingAmount() {
		return $this->shippingAmount;
	}

	/** @return string */
	public function getShippingDescription() {
		return $this->shippingDescription;
	}

	/**
	 * @param StoreModuleOrderTax[] $taxes
	 * @return StoreModuleOrder
	 */
	public function setTaxes(array $taxes) {
		$this->taxes = $taxes;
		return $this;
	}

	/**
	 * @param float $shippingAmount
	 * @return StoreModuleOrder
	 */
	public function setShippingAmount($shippingAmount) {
		$this->shippingAmount = $shippingAmount;
		return $this;
	}

	/**
	 * @param string $shippingDescription
	 * @return $this
	 */
	public function setShippingDescription($shippingDescription) {
		$this->shippingDescription = $shippingDescription;
		return $this;
	}

	/** @return float */
	public function getDiscountAmount() {
		return $this->discountAmount;
	}

	/**
	 * @param float $discountAmount
	 * @return self
	 */
	public function setDiscountAmount($discountAmount) {
		$this->discountAmount = $discountAmount;
		return $this;
	}

	/** @return string */
	public function getOrderComment() {
		return $this->orderComment;
	}

	/**
	 * @param string $orderComment
	 * @return StoreModuleOrder
	 */
	public function setOrderComment($orderComment) {
		$this->orderComment = $orderComment;
		return $this;
	}

	/** @return StoreCurrency */
	public function getCurrency() {
		return $this->currency;
	}

	/** @return StorePriceOptions */
	public function getPriceOptions() {
		return $this->priceOptions;
	}

	/** @return StoreModuleOrder */
	public function setCurrency(StoreCurrency $currency = null) {
		$this->currency = $currency;
		return $this;
	}

	/** @return StoreModuleOrder */
	public function setPriceOptions(StorePriceOptions $priceOptions = null) {
		$this->priceOptions = $priceOptions;
		return $this;
	}

	public function getCustomFields() {
		return $this->customFields;
	}

	public function setCustomField($name, $value) {
		$this->customFields[$name] = $value;
	}

	public function getCustomField($name, $default = null) {
		if (isset($this->customFields[$name])) return $this->customFields[$name];
		return $default;
	}

	public function getInvoiceDocumentNumber() {
		return $this->invoiceDocumentNumber;
	}

	/** @return bool */
	public function getStockManaged() {
		return $this->stockManaged;
	}

	/**
	 * @param bool $stockManaged
	 * @return self
	 */
	public function setStockManaged($stockManaged) {
		$this->stockManaged = $stockManaged;
		return $this;
	}

	/** @return int */
	public function getStockAppliedVersion() {
		return $this->stockAppliedVersion;
	}

	/** @param int $stockAppliedVersion */
	public function setStockAppliedVersion($stockAppliedVersion) {
		$this->stockAppliedVersion = $stockAppliedVersion;
	}

	/** @return ?StoreCoupon */
	public function getCoupon() {
		return $this->coupon;
	}

	/** @return self */
	public function setCoupon(StoreCoupon $coupon = null) {
		$this->coupon = $coupon;
		return $this;
	}

	private static function getHashInternal($id, $transactionId, $dateTime) {
		// spell-checker: disable
		return sha1("{$id}/{$transactionId}/{$dateTime}/C2s98&HfoAs87b0W(*mcvozpDe6rU-");
		// spell-checker: enable
	}

	public function getHash() {
		return self::getHashInternal($this->id, $this->transactionId, $this->dateTime);
	}

	/**
	 * @return $this
	 */
	public function saveAttachments()
	{
		$fields = isset($this->billingForm) ? $this->billingForm : [];
		foreach ($fields as $idx => $field) {
			$fieldName = "wb_input_$idx";

			if (!is_object($field)) $field = (object)$field;
			if ($field->type === 'file' && isset($this->billingInfo->{$fieldName})) {
				if (!isset($field->settings->fileMultiple) || !$field->settings->fileMultiple) {
					$value = $this->billingInfo->{$fieldName};
					$this->billingInfo->{$fieldName} = $this->saveFile($field, $value->name, $value->data);
				} elseif (is_array($this->billingInfo->{$fieldName})) {
					foreach ($this->billingInfo->{$fieldName} as &$item) {
						$item = $this->saveFile($field, $item->name, $item->data);
					}
				}
			}

			if ($field->type === 'file' && isset($this->deliveryInfo->{$fieldName})) {
				if (!isset($field->settings->fileMultiple) || !$field->settings->fileMultiple) {
					$value = $this->deliveryInfo->{$fieldName};
					$this->deliveryInfo->{$fieldName} = $this->saveFile($field, $value->name, $value->data);
				} elseif (is_array($this->deliveryInfo->{$fieldName})) {
					foreach ($this->deliveryInfo->{$fieldName} as &$item) {
						$item = $this->saveFile($field, $item->name, $item->data);
					}
				}
			}
		}

		foreach ($this->items as $item) {
			foreach ($item->files as $file) {
				$file->saveFile($this);
			}
		}

		return $this;
	}

	protected function saveFile($field, $fileName, $fileData)
	{
		if ($field->enabled && isset($field->settings->fileSaving) && $field->settings->fileSaving) {

			$attachmentsLogDir = dirname(__FILE__) . DIRECTORY_SEPARATOR . '..' . DIRECTORY_SEPARATOR . '..' . DIRECTORY_SEPARATOR . "forms_log_attachments" . DIRECTORY_SEPARATOR . "store" . DIRECTORY_SEPARATOR . $this->transactionId;
			if (!file_exists($attachmentsLogDir)) {
				if (!mkdir($attachmentsLogDir, 0755, true)) {
					error_log('[Store error]: Failed to create a directory for attachments');
					return null;
				}
			}
			if (!is_dir($attachmentsLogDir) || !is_dir($attachmentsLogDir)) {
				error_log('[Store error]: Attachments inode on the server is not a directory');
				return null;
			}


			$secureFileName = $fileName;
			$secureFileName = preg_replace("#[\\\\/<>\\?;:,=]+#isu", "_", $secureFileName);
			$secureFileName = preg_replace("#\\.\\.+#isu", ".", $secureFileName);
			$tmpCopyName = $attachmentsLogDir . DIRECTORY_SEPARATOR . $secureFileName;

			$data = base64_decode(preg_replace('#^data:.+?;base64,#i', '', $fileData));

			if (!file_put_contents($tmpCopyName, $data)) {
				error_log('[Form error]: Failed to move uploaded file to attachments directory');
				return null;
			}
			return '/store/' . $this->transactionId . '/' . $secureFileName;
		}
		return null;
	}

	public function save() {
		self::lockLogFile(true);
		$orderLog = self::readLogFile();
		if ($this->id) {
			foreach ($orderLog->items as $idx => $liArr) {
				if (isset($liArr['id']) && $liArr['id'] == $this->id) {
					$orderLog->items[$idx] = $this->jsonSerialize(); break;
				}
			}
		} else {
			$this->generateInvoiceDocumentNumber();
			$thisArr = $this->jsonSerialize();
			$newId = self::getNewId($orderLog->items);
			$thisArr['id'] = $newId;
			$orderLog->items[] = $thisArr;
			$this->id = $newId;
		}
		$result = (self::writeLogFile($orderLog)) ? $this->id : null;
		self::unlockLogFile();
		return $result;
	}

	/** @return bool */
	public function delete() {
		$deleted = false;
		if( $this->id ) {
			self::lockLogFile(true);
			$orderLog = self::readLogFile();
			foreach ($orderLog->items as $idx => $liArr) {
				if (isset($liArr['id']) && $liArr['id'] == $this->id) {
					array_splice($orderLog->items, $idx, 1);
					$deleted = true;
					break;
				}
			}
			if ($deleted) self::writeLogFile($orderLog);
			self::unlockLogFile();
		}
		return $deleted;
	}

	/** @return int */
	private static function getNewId(array &$listArr) {
		$max = 0;
		foreach ($listArr as $liArr) {
			if (is_numeric($liArr['id']) && (!$max || $max < intval($liArr['id']))) {
				$max = intval($liArr['id']);
			}
		}
		return (++$max);
	}

	/** @return StoreModuleOrder */
	public static function findByTransactionId($transactionId) {
		if (!$transactionId) return null;
		$list = self::findAll(array(self::FILTER_TRANSACTION_ID => $transactionId));
		return array_shift($list);
	}

	/** @return StoreModuleOrder */
	public static function findByExtTransactionId($extTransactionId) {
		if (!$extTransactionId) return null;
		$list = self::findAll(array(self::FILTER_EXT_TRANSACTION_ID => $extTransactionId));
		return array_shift($list);
	}

	/** @return StoreModuleOrder */
	public static function findByHash($hash) {
		if (!$hash) return null;
		$list = self::findAll(array(self::FILTER_HASH => $hash));
		return array_shift($list);
	}

	public static function findById($id) {
		if (!$id) return null;
		$list = self::findAll(array(self::FILTER_ID => $id));
		return array_shift($list);
	}

	/** @return StoreModuleOrder[] */
	public static function findAll(array $filter = array(), $limit = null) {
		$list = array();
		self::lockLogFile(false);
		$orderLog = self::readLogFile();
		self::unlockLogFile();
		foreach ($orderLog->items as $f) {
			if( $limit !== null ) {
				if( $limit <= 0 )
					break;
				$limit--;
			}
			if ($filter && is_array($filter)) {
				if (isset($filter[self::FILTER_ID]) && $filter[self::FILTER_ID]
					&& (!isset($f['id']) || $f['id'] != $filter[self::FILTER_ID])) continue;
				if (isset($filter[self::FILTER_TRANSACTION_ID]) && $filter[self::FILTER_TRANSACTION_ID]
					&& (!isset($f['transactionId']) || $f['transactionId'] != $filter[self::FILTER_TRANSACTION_ID])) continue;
				if (isset($filter[self::FILTER_EXT_TRANSACTION_ID]) && $filter[self::FILTER_EXT_TRANSACTION_ID]
					&& (!isset($f['extTransactionId']) || $f['extTransactionId'] != $filter[self::FILTER_EXT_TRANSACTION_ID])) continue;
				if (isset($filter[self::FILTER_HASH]) && $filter[self::FILTER_HASH]
					&& (!isset($f['id'], $f['transactionId'], $f['dateTime']) || self::getHashInternal($f['id'], $f['transactionId'], $f['dateTime']) != $filter[self::FILTER_HASH])) continue;
				if (isset($filter[self::FILTER_STATE]) && $filter[self::FILTER_STATE]
					&& (!isset($f['state']) || $f['state'] != $filter[self::FILTER_STATE])) continue;
				if (isset($filter[self::FILTER_DATE_TIME_LTE]) && $filter[self::FILTER_DATE_TIME_LTE]
					&& (!isset($f['dateTime']) || $f['dateTime'] > $filter[self::FILTER_DATE_TIME_LTE])) continue;
				if (isset($filter[self::FILTER_DATE_TIME_GTE]) && $filter[self::FILTER_DATE_TIME_GTE]
					&& (!isset($f['dateTime']) || $f['dateTime'] < $filter[self::FILTER_DATE_TIME_GTE])) continue;
			}
			$o = new self();
			$o->populate($f);
			$list[] = $o;
		}
		return $list;
	}

	/**
	 * @param int $applyVersion
	 * @return bool
	 */
	public function isStockApplicable($applyVersion) {
		return ($this->stockManaged
			&& ($this->stockAppliedVersion <= 0 || $this->stockAppliedVersion > $applyVersion)
			&& in_array($this->state, array(self::STATE_PENDING, self::STATE_PAID, self::STATE_COMPLETE)));
	}

	/**
	 * @param StoreModuleOrderItem[]|string[] $items
	 * @param int[] $result
	 * @return void
	 */
	public static function indexStockChangesFromItems(array $items, array &$result) {
		foreach ($items as $item) {
			if (!is_object($item) || !is_string($item->sku) || empty($item->sku) || $item->quantity <= 0) {
				continue;
			}
			if (!isset($result[$item->sku])) $result[$item->sku] = 0;
			$result[$item->sku] += $item->quantity;
		}
	}

	/**
	 * @param int $applyVersion
	 * @param bool $saveApplication
	 * @return array
	 */
	public static function indexStockChanges($applyVersion, $saveApplication = false) {
		$newApplyVersion = 1;
		self::lockLogFile($saveApplication);
		{
			$orderLog = self::readLogFile();
			$newApplyVersion = $orderLog->stockAppliedVersion + 1;

			$indexes = array();
			$result = array();
			foreach ($orderLog->items as $idx => $f) {
				$order = new self(); $order->populate($f);
				if ($newApplyVersion <= $order->stockAppliedVersion) {
					$newApplyVersion = $order->stockAppliedVersion + 1;
				}
				if ($order->isStockApplicable($applyVersion)) {
					self::indexStockChangesFromItems($order->items, $result);
					if ($order->stockAppliedVersion <= 0) $indexes[] = $idx;
				}
			}

			if ($saveApplication && !empty($indexes)) {
				foreach ($indexes as $idx) {
					$orderLog->items[$idx]['stockAppliedVersion'] = $newApplyVersion;
				}
				$orderLog->stockAppliedVersion = $newApplyVersion;
				self::writeLogFile($orderLog);
			} else {
				// If new version was not used return last that was
				$newApplyVersion = $orderLog->stockAppliedVersion;
			}
		}
		self::unlockLogFile();

		return [$result, $newApplyVersion];
	}

	/** @return StoreModuleOrderLogData */
	private static function readLogFile() {
		$result = new StoreModuleOrderLogData();
		$result->items = [];
		try {
			$itemsFile = StoreModule::getLogFile();
			if (is_file($itemsFile)) {
				$contents = '';
				if (($fh = @fopen($itemsFile, 'r')) !== false) {
					while (!feof($fh)) {
						$contents .= fread($fh, 2048);
					}
					fclose($fh);
				} else {
					throw new ErrorException('Error: Failed reading log file');
				}
				$r = json_decode($contents, true);
				if (!is_array($r)) {
					throw new ErrorException('Error: Failed parsing orders log file');
				}
				if (isset($r['stockAppliedVersion']) && is_int($r['stockAppliedVersion']) && $r['stockAppliedVersion'] > 0) {
					$result->stockAppliedVersion = $r['stockAppliedVersion'];
				}
				if (isset($r['items']) && is_array($r['items'])) {
					$result->items = $r['items'];
				} else if (!isset($r['items']) && isset($r[0])) {
					// Note: convert from old format
					$result->items = $r;
				}
			}

			$itemsFile = StoreModule::getLogFileJsonl();
			if (is_file($itemsFile)) {
				if (($fh = @fopen($itemsFile, 'r')) !== false) {
					while (!feof($fh)) {
						$contents = fgets($fh);
						if ($contents !== false) {
							$contents = json_decode($contents, true);
							if ($contents === null) {
								throw new ErrorException('Error: Failed parsing orders log file');
							}
							$result->items[] = $contents;
						}
					}
					fclose($fh);
				} else {
					throw new ErrorException('Error: Failed reading log file');
				}
			}
		} catch (ErrorException $ex) {
			error_log($ex->getMessage());
		}
		return $result;
	}

	/** @return bool */
	private static function writeLogFile(StoreModuleOrderLogData $data) {
		try {
			$itemsFile = StoreModule::getLogFileJsonl();
			$logFile = StoreModule::getLogFile();
			if (!is_file($itemsFile) && is_file($logFile)) { // @note: backup old log file
				rename($logFile, $logFile.'.bak');
			}

			// before updating items log file, backup it.
			if (is_file($itemsFile) && (!is_file($itemsFile.'.bak') || is_writable($itemsFile.'.bak'))) {
				copy($itemsFile, $itemsFile.'.bak');
			}

			if (($fh = fopen($itemsFile, 'w')) !== false) {
				foreach ($data->items as $f) {
					$json = json_encode($f);
					if ($json === null || $json === false) {
						file_put_contents(dirname($itemsFile).'/corrupted-orders.log', '['.date('Y-m-d H:i:s').'] ' . serialize($f) . "\n", FILE_APPEND);
						throw new ErrorException('Error: Failed encoding orders log file');
					}
					fwrite($fh, $json .  PHP_EOL);
				}
				fclose($fh);
			} else {
				throw new ErrorException('Error: Failed writing log file');
			}

			$data->items = [];
			$itemsFile = StoreModule::getLogFile();
			$json = json_encode($data);
			if ($json === null || $json === false) {
				throw new ErrorException('Error: Failed encoding orders log file');
			} else if (($fh = fopen($itemsFile, 'w')) !== false) {
				fwrite($fh, $json);
				fclose($fh);
			} else {
				throw new ErrorException('Error: Failed writing log file');
			}

			return true;
		} catch (ErrorException $ex) {
			error_log($ex->getMessage());
		}
		return false;
	}

	public function fromJson($data) {
		$this->populate($data);
	}

	public function jsonSerialize() {
		$items = array();
		foreach( $this->items as $k => $item )
			$items[$k] = ($item instanceof StoreModuleOrderItem) ? $item->jsonSerialize() : $item;
		return array(
			'id' => $this->id,
			'transactionId' => $this->transactionId,
			'extTransactionId' => $this->extTransactionId,
			'hash' => $this->getHash(),
			'invoiceDocumentNumber' => $this->invoiceDocumentNumber,
			'stockManaged' => $this->stockManaged,
			'stockAppliedVersion' => $this->stockAppliedVersion,
			'coupon' => $this->coupon,
			'gatewayId' => $this->gatewayId,
			'lang' => $this->lang,
			'buyer' => ($this->buyer ? $this->buyer->jsonSerialize() : null),
			'items' => $items,
			'price' => $this->price,
			'type' => $this->type,
			'state' => $this->state,
			'dateTime' => $this->dateTime,
			'completeDateTime' => $this->completeDateTime,
			'cancelDateTime' => $this->cancelDateTime,
			'stateDateTime' => $this->stateDateTime,
			'billingForm' => ($this->billingForm ? $this->billingForm : null),
			'billingInfo' => ($this->billingInfo ? $this->billingInfo->jsonSerialize() : null),
			'deliveryInfo' => ($this->deliveryInfo ? $this->deliveryInfo->jsonSerialize() : null),
			'currency' => ($this->currency ? $this->currency->jsonSerialize() : null),
			'priceOptions' => ($this->priceOptions ? $this->priceOptions->jsonSerialize() : null),
			'orderComment' => $this->orderComment,
			'taxes' => $this->taxes,
			'shippingAmount' => $this->shippingAmount,
			'shippingDescription' => $this->shippingDescription,
			'discountAmount' => $this->discountAmount,
			'customFields' => $this->customFields,
			'invoiceON' => $this->invoiceON,
			'invoiceResended' => $this->invoiceResended
		);
	}

	public function jsonSerializeApi() {
		$result = (object) $this->jsonSerialize();

		if (isset($result->buyer)) {
			if (is_array($result->buyer) && isset($result->buyer[0])) {
				$arr = $result->buyer;
				$result->buyer = (object) array();
				if (isset($arr[0]) && is_string($arr[0])) $result->buyer->Name = $arr[0];
				if (isset($arr[1]) && is_string($arr[1])) $result->buyer->Email = $arr[1];
				if (isset($arr[2]) && is_string($arr[2])) $result->buyer->Address = $arr[2];
			} else {
				$obj = (object) $result->buyer;
				$changed = false;
				if (isset($obj->name) && !isset($obj->Name)) {
					$obj->Name = $obj->name;
					unset($obj->name);
					$changed = true;
				}
				// spell-checker: ignore İsim, E-posta, Adres
				if (isset($obj->{'İsim'}) && !isset($obj->Name)) {
					$obj->Name = $obj->{'İsim'};
					unset($obj->{'İsim'});
					$changed = true;
				}
				if (isset($obj->email) && !isset($obj->Email)) {
					$obj->Email = $obj->email;
					unset($obj->email);
					$changed = true;
				}
				if (isset($obj->{'E-posta'}) && !isset($obj->Email)) {
					$obj->Email = $obj->{'E-posta'};
					unset($obj->{'E-posta'});
					$changed = true;
				}
				if (isset($obj->address) && !isset($obj->Address)) {
					$obj->Address = $obj->address;
					unset($obj->address);
					$changed = true;
				}
				if (isset($obj->{'Adres'}) && !isset($obj->Address)) {
					$obj->Address = $obj->{'Adres'};
					unset($obj->{'Adres'});
					$changed = true;
				}
				if ($changed) {
					$result->buyer = $obj;
				}
			}
		}

		$result->taxAmount = $totalTaxAmount = $this->getFullTaxAmount();

		if (isset($result->items) && is_array($result->items)) {
			$orderItemsCount = count($result->items);
			$totalAmount = $this->getPrice();
			$taxRate = round($totalTaxAmount / ($totalAmount - $totalTaxAmount) * 100) / 100;
			$shippingAmount = round($this->getShippingAmount() * (1 + $taxRate) * 100) / 100;
			// Note: tax system became more complicated and conditional and at this point
			// too much information is lost to correctly calculate this price.
			// So only the most basic tax configuration will produce correct results here.
			$correctionAmount = $totalAmount - $shippingAmount;
			for ($i = 0; $i < $orderItemsCount; $i++) {
				if (is_string($result->items[$i])) continue;
				$item = $result->items[$i] = (object) $result->items[$i];

				$priceWithTaxes = round($item->price * (1 + $taxRate) * 100) / 100;
				if ($orderItemsCount == ($i + 1)) {
					$priceWithTaxes = round($correctionAmount / $item->quantity * 100) / 100;
				} else {
					$correctionAmount -= $priceWithTaxes * $item->quantity;
				}
				$item->priceWithTaxes = $priceWithTaxes;
			}
		}

		return $result;
	}

	/**
	 * @param bool $forWriting
	 * @param bool $blocking
	 * @return bool|null Returns NULL if lock file could not be created or opened, TRUE if lock succeeded and FALSE if there was an error or locking did not block while $block parameter was set to FALSE.
	 */
	private static function lockLogFile($forWriting, $blocking = true) {
		if( self::$logLockFile === null )
			self::$logLockFile = @fopen(StoreModule::getLogFile() . ".lock", "c");
		if( !self::$logLockFile )
			return null;
		return @flock(self::$logLockFile, ($forWriting ? LOCK_EX : LOCK_SH) | ($blocking ? 0 : LOCK_NB));
	}

	private static function unlockLogFile() {
		if( !self::$logLockFile )
			return;
		@flock(self::$logLockFile, LOCK_UN);
	}

	public function generateInvoiceDocumentNumber() {
		foreach( $this->items as $item )
			if( !$item instanceof StoreModuleOrderItem )
				return null;
		return $this->invoiceDocumentNumber = StoreModule::getNextInvoiceDocumentNumber(StoreData::getInvoiceDocumentNumberFormat());
	}
}

final class StoreModuleOrderLogData {
	/** @var int   */ public $stockAppliedVersion = 0;
	/** @var array */ public $items = array();
}

class StoreModuleOrderTax {
	/** @var float */ public $rate = 0;
	/** @var float */ public $amount = 0;
	/** @var bool  */ public $shippingOnly = false;

	/**
	 * @param float $rate
	 * @param float $amount
	 * @param bool $shippingOnly
	 */
	public function __construct($rate = 0, $amount = 0, $shippingOnly = false) {
		$this->rate = $rate;
		$this->amount = $amount;
		$this->shippingOnly = $shippingOnly;
	}

	/** @return float */
	public function getRatePercent() {
		return round($this->rate * 100, 2);
	}

	/**
	 * @param object $data
	 * @return ?self
	 */
	public static function fromJson($data) {
		if (!isset($data->amount) || !is_numeric($data->amount) || $data->amount <= 0) {
			return null;
		}
		return new self(
			((isset($data->rate) && is_numeric($data->rate) && $data->rate > 0)
				? floatval($data->rate)
				: 0),
			floatval($data->amount),
			(isset($data->shippingOnly) && $data->shippingOnly));
	}
}
