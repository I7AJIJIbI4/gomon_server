<?php

class StoreModuleOrderItemFiles {
	/** @var string */
	public $name = "";
	/** @var string */
	public $src = "";
	/** @var string */
	public $orderedSrc = "";
	/** @var string */
	public $extension = "";

	public function __construct($name, $src, $extension, $orderedSrc = null) {
		$this->name = $name;
		$this->src = $src;
		$this->extension = $extension;
		$this->orderedSrc = $orderedSrc;
	}

	/**
	 * @param stdClass|array $data
	 * @return StoreModuleOrderItemFiles
	 */
	public static function fromJson($data) {
		if( !is_object($data) )
			$data = (object)$data;
		return new self($data->name, $data->src, $data->extension, isset($data->orderedSrc) ? $data->orderedSrc : null);
	}

	public function jsonSerialize() {
		return array(
			"name" => $this->name,
			"src" => $this->src,
			"extension" => $this->extension,
			"orderedSrc" => $this->orderedSrc,
		);
	}

	public function __toString() {
		return "{$this->name} ({$this->extension}, {$this->getFileSize()})";
	}

	public function getExtension($format = false)
	{
		if ($format) {
			return strtoupper($this->extension);
		}
		return $this->extension;
	}

	public function getFile()
	{
		return realpath(__DIR__.'/../..').DIRECTORY_SEPARATOR.$this->src;
	}

	public function getOrderedFile()
	{
		return realpath(__DIR__.'/../..').DIRECTORY_SEPARATOR.$this->orderedSrc;
	}

	public function getFileSize($decimals = 2)
	{
		$bytes = filesize($this->getFile());

		$sz = 'BKMGTP';
		$factor = (int)floor((strlen($bytes) - 1) / 3);
		return sprintf("%.{$decimals}f", $bytes / pow(1024, $factor)) . @$sz[$factor];
	}

	public function saveFile(StoreModuleOrder $order)
	{
		$attachmentDir = dirname(__FILE__) . DIRECTORY_SEPARATOR . '..' . DIRECTORY_SEPARATOR . '..' . DIRECTORY_SEPARATOR;

		$secureFileName = $this->name . '.' . $this->extension;
		$secureFileName = preg_replace("#[\\\\/<>\\?;:,=]+#isu", "_", $secureFileName);
		$secureFileName = preg_replace("#\\.\\.+#isu", ".", $secureFileName);
		$targetFilePath = "store_log_attachments" . DIRECTORY_SEPARATOR . "store" . DIRECTORY_SEPARATOR . $order->getHash() . DIRECTORY_SEPARATOR . $secureFileName;

		$attachmentsLogDir = dirname($attachmentDir . $targetFilePath);
		if (!file_exists($attachmentsLogDir)) {
			if (!mkdir($attachmentsLogDir, 0755, true)) {
				error_log('[Store error]: Failed to create a directory for attachments');
				return false;
			}
		}
		if (!is_dir($attachmentsLogDir) || !is_dir($attachmentsLogDir)) {
			error_log('[Store error]: Attachments inode on the server is not a directory');
			return false;
		}

		if (!copy($this->getFile(), $attachmentDir . $targetFilePath)) {
			error_log('[Form error]: Failed to move uploaded file to attachments directory');
			return false;
		}
		$this->orderedSrc = $targetFilePath;
		return true;
	}
}