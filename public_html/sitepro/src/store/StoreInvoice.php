<?php

class StoreInvoice extends TCPDF {
	const PAGE_MARGIN_LEFT = 15;
	const PAGE_MARGIN_RIGHT = 15;
	const PAGE_MARGIN_TOP = 15;
	const PAGE_MARGIN_BOTTOM = 25; // footer is inside this margin
	const PAGE_MARGIN_FOOTER = 5;

	public $footerTextLeft = "";
	public $footerTextCenter = "";
	public $footerTextRight = "";

	/**
	 * IMPORTANT: Please note that this method sets the mb_internal_encoding to ASCII, so if you are using the mbstring module functions with TCPDF you need to correctly set/unset the mb_internal_encoding when needed.
	 *
	 * @inheritdoc
	 */
	public function __construct($orientation = 'P', $unit = 'mm', $format = 'A4', $unicode = true, $encoding = 'UTF-8', $diskcache = false, $pdfa = false) {
		parent::__construct($orientation, $unit, $format, $unicode, $encoding, $diskcache, $pdfa);

		// set default header data
		// $pdf->SetHeaderData(PDF_HEADER_LOGO, PDF_HEADER_LOGO_WIDTH, PDF_HEADER_TITLE.' 001', PDF_HEADER_STRING, array(0,64,255), array(0,64,128));
		// $pdf->setFooterData(array(0,64,0), array(0,64,128));

		// set header and footer fonts
		$this->setHeaderFont(Array(PDF_FONT_NAME_MAIN, '', PDF_FONT_SIZE_MAIN));
		$this->setFooterFont(Array('NotoSans', '', PDF_FONT_SIZE_MAIN));

		$this->setPrintHeader(false);
		$this->setPrintFooter(true);

		// set default monospaced font
		$this->SetDefaultMonospacedFont(PDF_FONT_MONOSPACED);

		// set margins
		$this->SetMargins(self::PAGE_MARGIN_LEFT, self::PAGE_MARGIN_TOP, self::PAGE_MARGIN_RIGHT);
		$this->SetHeaderMargin(0);
		$this->SetFooterMargin(self::PAGE_MARGIN_FOOTER);

		// set auto page breaks
		$this->SetAutoPageBreak(TRUE, self::PAGE_MARGIN_BOTTOM);

		// set image scale factor
		$this->setImageScale(PDF_IMAGE_SCALE_RATIO);

		// ---------------------------------------------------------

		// set default font subsetting mode
		$this->setFontSubsetting(true);

		// Set font
		// dejavusans is a UTF-8 Unicode font, if you only need to
		// print standard ASCII chars, you can use core fonts like
		// helvetica or times to reduce file size.
		// $this->SetFont(PDF_FONT_NAME_MAIN, '', PDF_FONT_SIZE_MAIN, '', true);
		// $this->SetFont('dejavusans', '', PDF_FONT_SIZE_MAIN, '', true);
		$this->SetFont('NotoSans', '', PDF_FONT_SIZE_MAIN, '', true);
		// set text shadow effect
		// $pdf->setTextShadow(array('enabled'=>true, 'depth_w'=>0.2, 'depth_h'=>0.2, 'color'=>array(196,196,196), 'opacity'=>1, 'blend_mode'=>'Normal'));

		$this->footerTextCenter = sprintf(StoreModule::__('Page %1$s of %2$s'), '{page}', '{numPages}');
	}

	public function Footer() {
		$y = $this->y;
		$this->SetTextColorArray($this->footer_text_color);
		//set style for cell border
		// $line_width = (0.85 / $this->k);
		// $this->SetLineStyle(array('width' => $line_width, 'cap' => 'butt', 'join' => 'miter', 'dash' => 0, 'color' => $this->footer_line_color));

		$margins = $this->getMargins();
		$width = $this->getPageWidth() - $margins["left"] - $margins["right"];
		$height = $this->getPageHeight();

		$text = strtr($this->footerTextLeft, array(
			'{page}' => empty($this->pagegroups) ? $this->PageNo() : $this->getGroupPageNo(),
			'{numPages}' => $this->getAliasNbPages(),
		));
		if( $text !== '' ) {
			$this->SetXY($this->original_lMargin, $y);
			$this->writeHTMLCell($width, 0, $margins["left"], $height - $margins["bottom"] + $margins["footer"], self::fontize($text), 0, 0, false, true, 'L', false);
		}

		$text = strtr($this->footerTextCenter, array(
			'{page}' => empty($this->pagegroups) ? $this->PageNo() : $this->getGroupPageNo(),
			'{numPages}' => $this->getAliasNbPages(),
		));
		if( $text !== '' ) {
			$this->SetXY($this->original_lMargin, $y);
			$this->writeHTMLCell($width, 0, $margins["left"], $height - $margins["bottom"] + $margins["footer"], self::fontize($text), 0, 0, false, true, 'C', false);
		}

		$text = strtr($this->footerTextRight, array(
			'{page}' => empty($this->pagegroups) ? $this->PageNo() : $this->getGroupPageNo(),
			'{numPages}' => $this->getAliasNbPages(),
		));
		if( $text !== '' ) {
			$this->SetXY($this->original_lMargin, $y);
			$this->writeHTMLCell($width, 0, $margins["left"], $height - $margins["bottom"] + $margins["footer"], self::fontize($text), 0, 0, false, true, 'R', false);
		}
	}

	public static function fontize($text) {
		$currentFont = null;
		$outText = "";
		for( $i = 0, $il = mb_strlen($text, "utf-8"); $i < $il; $i++ ) {
			$char = mb_substr($text, $i, 1, "utf-8");
			$font = FontCharMap::getCharFont($char);
			if( $currentFont !== $font && $char !== " " ) {
				if( $currentFont !== null ) {
					$done = false;
					$outText = preg_replace_callback("#(\\s*)$#isu", function($mtc) use(&$done) {
						if( $done )
							return "";
						$done = true;
						return "</span>" . $mtc[1];
					}, $outText);
				}
				$currentFont = $font;
				if( $currentFont !== null )
					$outText .= "<span style=\"font-family:{$currentFont};\">";
			}
			$outText .= $char;
		}
		if( $currentFont !== null ) {
			$done = false;
			$outText = preg_replace_callback("#(\\s*)$#isu", function($mtc) use(&$done) {
				if( $done )
					return "";
				$done = true;
				return "</span>" . $mtc[1];
			}, $outText);
		}
		return $outText;
	}

}